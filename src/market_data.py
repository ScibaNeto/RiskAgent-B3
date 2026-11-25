"""Ingestão local de fechamentos ajustados com trilha de qualidade e snapshots."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import tempfile
import time
from uuid import uuid4
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from filelock import FileLock

if __package__:
    from .b3_sessions import completed_sessions, daily_log_returns
else:
    from b3_sessions import completed_sessions, daily_log_returns

LOG = logging.getLogger("riskagent.data")
DEFAULT_MAX_STALE_SESSIONS = 1


def _date_label(value):
    """Daily bars may use local midnight or its UTC representation."""
    try:
        stamp = pd.Timestamp(value)
        if stamp.tzinfo is not None:
            if stamp != stamp.normalize():
                stamp = stamp.tz_convert("America/Sao_Paulo")
            stamp = stamp.tz_localize(None)
        return stamp if pd.notna(stamp) and stamp == stamp.normalize() else pd.NaT
    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def clean_prices(series: pd.Series, name: str, today: pd.Timestamp) -> tuple[pd.Series, dict]:
    if isinstance(series.index, pd.DatetimeIndex) and series.index.tz is None:
        labels = series.index.where(series.index == series.index.normalize())
    else:
        labels = pd.DatetimeIndex([_date_label(value) for value in series.index])
    try:
        values = series.to_numpy(dtype=float, na_value=np.nan)
    except (ValueError, TypeError):
        values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    date_ok = labels.notna() & (labels <= today)
    price_ok = np.isfinite(values) & (values > 0)
    cleaned = pd.Series(values[date_ok & price_ok], index=labels[date_ok & price_ok], name=name)
    checks = {
        "rows": len(series),
        "invalid_or_intraday_dates": int(labels.isna().sum()),
        "future_dates": int((labels > today).sum()),
        "null_or_nonfinite_prices": int((~np.isfinite(values)).sum()),
        "nonpositive_prices": int((values <= 0).sum()),
        "duplicate_dates": int(cleaned.index.duplicated().sum()),
        "out_of_order": not cleaned.index.is_monotonic_increasing,
        "invalid_rows": int((~(date_ok & price_ok)).sum()),
    }
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")].sort_index()
    if cleaned.empty:
        raise ValueError(f"Nenhum preco positivo com data valida para {name}.")
    return cleaned, checks


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with tmp_path.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_json(path: Path, data: dict) -> None:
    atomic_bytes(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


@dataclass
class MarketInput:
    prices: pd.Series
    returns: pd.Series
    record: dict


def add_data_arguments(parser) -> None:
    parser.add_argument("--offline", action="store_true", help="usa apenas o cache local")
    parser.add_argument("--strict-cache", action="store_true", help="interrompe se o atraso exceder o limite")
    parser.add_argument("--max-stale-sessions", type=int, default=DEFAULT_MAX_STALE_SESSIONS,
                        help="máximo de pregões encerrados em atraso no modo estrito (padrão: 1)")


def _read_cache(payload: bytes | None, name: str, today: pd.Timestamp, record: dict) -> pd.Series:
    cached = pd.Series(dtype=float, name=name)
    if payload is not None:
        try:
            frame = pd.read_csv(io.BytesIO(payload), index_col=0, dtype=str)
            columns = [c for c in ("Close", "Adj Close", "price", name) if c in frame]
            if not columns and len(frame.columns) != 1:
                raise ValueError("Coluna de fechamento ambígua.")
            parsed, checks = clean_prices(frame[columns[0] if columns else frame.columns[0]], name, today)
            record["cache_checks"] = checks
            if checks["invalid_rows"] or checks["duplicate_dates"]:
                raise ValueError("Cache com datas duplicadas ou linhas inválidas.")
            cached = parsed
        except (ValueError, IndexError, UnicodeError) as exc:
            record["cache_error"] = str(exc)
            LOG.warning("%s: erro de leitura do cache: %s", name, exc)
    return cached


def _assess_history(raw: pd.Series, sessions: pd.DatetimeIndex, name: str, minimum: int,
                    strict: bool, max_stale_sessions: int):
    prices = raw.loc[raw.index.isin(sessions)]
    returns = daily_log_returns(prices)
    if len(returns) < minimum:
        raise HistoryRejected(f"Amostra insuficiente para {name}: {len(returns)} retornos validos; minimo {minimum}.", "incompleto")
    stale = int((sessions > prices.index[-1]).sum())
    if strict and stale > max_stale_sessions:
        raise HistoryRejected(f"Modo estrito: {name} está {stale} pregão(ões) em atraso; limite {max_stale_sessions}.", "desatualizado")
    internal = sessions[(sessions >= prices.index[0]) & (sessions <= prices.index[-1])]
    missing = internal.difference(prices.index)
    return prices, returns, {
        "coverage_status": "partial" if stale or len(missing) or (sessions[0] < prices.index[0]) else "complete",
        "freshness": "desatualizado" if stale else "atualizado",
        "completeness": "incompleto" if len(missing) or sessions[0] < prices.index[0] else "completo",
        "stale_sessions": stale, "missing_sessions": missing.strftime("%Y-%m-%d").tolist(),
        "excluded_dates": raw.index.difference(prices.index).strftime("%Y-%m-%d").tolist(),
        "missing_before_first_price": int((sessions < prices.index[0]).sum()),
        "extreme_return_dates": returns.index[returns.abs() > 15].strftime("%Y-%m-%d").tolist(),
    }


class HistoryRejected(RuntimeError):
    def __init__(self, message: str, status: str):
        super().__init__(message)
        self.status = status


def _quarantine(folder: Path, payload: bytes, metadata: dict, reason: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    event = folder / uuid4().hex
    with tempfile.TemporaryDirectory(dir=folder) as stage:
        packet = Path(stage) / "packet"
        atomic_bytes(packet / "payload.csv", payload)
        write_json(packet / "event.json", dict(metadata, reason=reason,
                   rejected_at_utc=pd.Timestamp.now(tz="UTC").isoformat(),
                   sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload)))
        os.replace(packet, event)
    return str(event)


def _fetch_sessions(begin: str, *, name: str, today: pd.Timestamp, sessions: pd.DatetimeIndex,
                    attempts: int, fetch: Callable, attempt_log: list, capture: Callable, reject: Callable) -> pd.Series:
    for attempt in range(1, attempts + 1):
        log = {"start": begin, "attempt": attempt}
        attempt_log.append(log)
        try:
            batch = fetch(begin)
            if batch is not None:
                capture(batch, begin, attempt)
            if batch is None or batch.empty:
                if batch is not None:
                    reject("Resposta vazia.")
                raise ValueError("Resposta vazia.")
        except Exception as exc:
            log["error"] = str(exc)
            if attempt == attempts:
                raise ConnectionError(f"Falha na coleta de {name}: {exc}") from exc
            time.sleep(min(5 * attempt, 15))
            continue
        if not isinstance(batch, pd.Series):
            raise ValueError("Coluna de fechamento ausente ou ambígua.")
        clean, checks = clean_prices(batch, name, today)
        log["checks"] = checks
        if checks["invalid_rows"] or checks["duplicate_dates"]:
            raise ValueError(f"Lote com linhas inválidas ou duplicadas: {checks}")
        usable = clean.loc[clean.index.isin(sessions)]
        log["excluded_dates"] = clean.index.difference(usable.index).strftime("%Y-%m-%d").tolist()
        if usable.empty:
            raise ValueError("Lote sem pregões encerrados válidos.")
        return usable


def ingest(name: str, *, cache_path: Path, start: str, minimum: int, overlap_days: int,
           fetch: Callable[[str], pd.Series], attempts: int = 1, offline: bool = False,
           strict: bool = False, max_stale_sessions: int = DEFAULT_MAX_STALE_SESSIONS,
           provider: str = "Yahoo Finance", symbol: str | None = None,
           as_of: pd.Timestamp | None = None, run_dir: Path | None = None) -> MarketInput:
    if max_stale_sessions < 0 or attempts < 1:
        raise ValueError("O limite de atraso deve ser não negativo e as tentativas pelo menos uma.")
    cutoff = pd.Timestamp.now(tz="UTC") if as_of is None else pd.Timestamp(as_of).tz_convert("UTC")
    today = cutoff.tz_convert("America/Sao_Paulo").tz_localize(None).normalize()
    sessions = completed_sessions(start, cutoff)
    if sessions.empty:
        raise ValueError("Nenhum pregão encerrado no período solicitado.")
    record = {"calendar": "BVMF", "as_of_utc": cutoff.isoformat(), "last_completed_session": str(sessions[-1].date()),
              "max_stale_sessions": max_stale_sessions, "strict": strict, "offline": offline,
              "collected_at_utc": None, "provider_attempts": [], "asset": name}
    folder = cache_path.parent / "quarantine" / cache_path.stem
    pending = []
    record["quarantine"] = []
    record["provider"] = provider
    record["requested_symbol"] = symbol or name

    def capture(batch, begin, attempt):
        pending.append((batch.to_csv(lineterminator="\n", na_rep="NaN").encode("utf-8"),
                        {"source": provider, "symbol": symbol or name, "start": begin, "attempt": attempt,
                         "format": "adapter_csv", "received_at_utc": pd.Timestamp.now(tz="UTC").isoformat()}))

    def reject(reason):
        for content, metadata in pending:
            record["quarantine"].append(_quarantine(folder, content, metadata, reason))
        pending.clear()

    payload = cache_path.read_bytes() if cache_path.is_file() else None
    cached = _read_cache(payload, name, today, record)
    if "cache_error" in record:
        record["quarantine"].append(_quarantine(folder, payload, {"source": "local_cache", "symbol": symbol or name,
            "format": "original_csv", "received_at_utc": pd.Timestamp.now(tz="UTC").isoformat()}, record["cache_error"]))
    cached_valid = cached.loc[cached.index.isin(sessions)]

    def download(begin: str) -> pd.Series:
        return _fetch_sessions(begin, name=name, today=today, sessions=sessions, attempts=attempts,
                               fetch=fetch, attempt_log=record["provider_attempts"], capture=capture, reject=reject)

    source = "cache_offline"
    candidate_payload = None
    try:
        if not offline:
            incremental = len(daily_log_returns(cached_valid)) >= minimum
            begin = max(pd.Timestamp(start), cached_valid.index[-1] - pd.Timedelta(days=overlap_days)) if incremental else pd.Timestamp(start)
            try:
                downloaded = download(str(begin.date()))
                common = cached_valid.index.intersection(downloaded.index).sort_values()
                revisions = common[~np.isclose(cached_valid.loc[common], downloaded.loc[common], rtol=1e-6, atol=0)]
                record["overlap_revisions"] = revisions.strftime("%Y-%m-%d").tolist()
                # Uma revisão na borda pode ser um ajuste corporativo de toda a série.
                full_refresh = incremental and (common.empty or common[0] in revisions)
                if full_refresh:
                    full = download(start)
                    if not downloaded.index.difference(full.index).empty or not np.allclose(
                        downloaded, full.reindex(downloaded.index), rtol=1e-6, atol=0
                    ):
                        raise ValueError("O histórico completo diverge do lote que motivou a nova coleta.")
                    downloaded = full
                if incremental and not full_refresh:
                    raw = pd.concat([cached, downloaded])
                    raw = raw[~raw.index.duplicated(keep="last")].sort_index()
                    source = "yahoo_finance_incremental+cache"
                else:
                    if not cached_valid.index.difference(downloaded.index).empty:
                        raise ValueError("Histórico completo perdeu datas válidas presentes no cache.")
                    raw = downloaded
                    source = "yahoo_finance_full_history"
                prices, returns, quality = _assess_history(raw, sessions, name, minimum, strict, max_stale_sessions)
                candidate_payload = raw.rename_axis("Date").to_frame("Close").to_csv(lineterminator="\n").encode("utf-8")
                record["collected_at_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
            except (ConnectionError, ValueError, RuntimeError) as exc:
                source = "cache_fallback_provider_unavailable" if isinstance(exc, ConnectionError) else "cache_fallback_download_invalid"
                reject(str(exc))
                record["provider_status"] = getattr(exc, "status", "indisponivel" if isinstance(exc, ConnectionError) else "invalido")
                record["fallback_reason"] = str(exc)
                LOG.warning("%s: %s; motivo: %s", name, source, exc)
        if candidate_payload is None:
            prices, returns, quality = _assess_history(cached, sessions, name, minimum, strict, max_stale_sessions)
            selected = payload
        else:
            selected = candidate_payload
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(str(cache_path) + ".lock", timeout=30):
                current = cache_path.read_bytes() if cache_path.is_file() else None
                if current != payload:
                    raise RuntimeError(f"Cache de {name} atualizado por outra execução. Repita a coleta.")
                if selected != current:
                    atomic_bytes(cache_path, selected)
        record.setdefault("provider_status", "sem_consulta" if offline else "valido")
        record.update(quality, source_mode=source, sha256=hashlib.sha256(selected).hexdigest())
        if run_dir is not None:
            snapshot = Path("inputs") / cache_path.name
            atomic_bytes(run_dir / snapshot, selected)
            record["snapshot"] = snapshot.as_posix()
        LOG.info("%s: %s; %s retornos, %s pregões ausentes e %s em atraso.",
                 name, source, len(returns), len(quality["missing_sessions"]), quality["stale_sessions"])
        if quality["stale_sessions"] > max_stale_sessions:
            LOG.warning("%s: atraso de %s pregões excede o limite de %s.", name, quality["stale_sessions"], max_stale_sessions)
        return MarketInput(prices, returns, record)
    except Exception as exc:
        if run_dir is not None:
            write_json(run_dir / "data_failure.json", dict(record, status="interrupted", data_status=(getattr(exc, "status", "indisponivel") if not cached.empty else ("invalido" if "cache_error" in record or record.get("provider_status") == "invalido" else "indisponivel")), source_mode=source, reason=str(exc)))
        raise
