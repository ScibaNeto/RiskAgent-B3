"""Consulta local de PETR4 com histórico diário separado das barras intradiárias."""
import gzip
import hashlib
import json
import logging
import math
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from .b3_sessions import _schedule, completed_sessions

SYMBOL = "PETR4.SA"
BASE = "https://query1.finance.yahoo.com/v8/finance/chart/PETR4.SA"
SOURCE = "Yahoo Finance"
ZONE = "America/Sao_Paulo"


def download(interval):
    span = "5d" if interval == "1m" else "3mo"
    url = f"{BASE}?range={span}&interval={interval}"
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8) as response:
        return response.read()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse_bars(payload, interval, now):
    chart = json.loads(payload)["chart"]
    if chart.get("error"):
        raise ValueError("Erro recebido do provedor.")
    result = chart["result"][0]
    meta = result["meta"]
    if (meta["symbol"], meta["currency"], meta["dataGranularity"]) != (SYMBOL, "BRL", interval):
        raise ValueError("Ativo, moeda ou intervalo inesperado.")
    times = result["timestamp"]
    quotes = result["indicators"]["quote"][0]
    bars = {}
    for stamp, close, volume in zip(times, quotes["close"], quotes["volume"], strict=True):
        instant = pd.Timestamp(stamp, unit="s", tz="UTC")
        if instant > now:
            raise ValueError("Barra futura.")
        if not number(close) or close <= 0:
            continue
        if volume is not None and (not number(volume) or volume < 0 or int(volume) != volume):
            raise ValueError("Volume inválido.")
        if instant in bars:
            raise ValueError("Minuto duplicado.")
        bars[instant] = (close, volume)
    if not bars:
        raise ValueError("Sem barras utilizáveis.")
    return bars


def session_info(now):
    day = now.tz_convert(ZONE).normalize().tz_localize(None)
    schedule = _schedule(day.year, day.year)
    if day not in schedule.index:
        return "Sem pregão hoje"
    session = schedule.loc[day]
    if now < session.open:
        return "Antes da abertura"
    return "Pregão em andamento" if now < session.close else "Pregão encerrado"


def quote_from(bars, now):
    sessions = _schedule(min(bars).year, now.year)
    for stamp in sorted(bars, reverse=True):
        day = stamp.tz_convert(ZONE).normalize().tz_localize(None)
        if day not in sessions.index:
            continue
        row = sessions.loc[day]
        if row.open <= stamp < row.close and stamp.second == 0 and stamp + pd.Timedelta(minutes=1) <= now:
            close, volume = bars[stamp]
            return dict(price=close, volume=volume, time=stamp.isoformat())
    raise ValueError("Sem minuto encerrado em sessão regular.")


def volume_from(bars, now):
    sessions = completed_sessions((now - pd.Timedelta(days=70)).date().isoformat(), now)
    values = {stamp.tz_convert(ZONE).normalize().tz_localize(None): vol for stamp, (_, vol) in bars.items()}
    last = max((day for day in sessions if values.get(day) is not None), default=None)
    if last is None:
        raise ValueError("Sem volume diário de pregão encerrado.")
    prior = sessions[sessions < last][-20:]
    samples = [values.get(day) for day in prior]
    average = sum(samples) / 20 if len(samples) == 20 and None not in samples else None
    return dict(date=str(last.date()), volume=values[last], mean20=average,
                expected_date=str(sessions[-1].date()))


class LiveMarket:
    def __init__(self, archive, fetch=download):
        self.archive = Path(archive)
        self.fetch = fetch
        self.lock = threading.Lock()
        self.next = {}
        self.state = {}

    def refresh(self, interval):
        parse = quote_from if interval == "1m" else volume_from
        payload = self.fetch(interval)
        now = pd.Timestamp.now(tz="UTC")
        digest = hashlib.sha256(payload).hexdigest()
        previous = self.state.get(interval, {})
        try:
            value = parse(parse_bars(payload, interval, now), now)
            key = "time" if interval == "1m" else "date"
            if previous.get("value") and value[key] < previous["value"][key]:
                raise ValueError("Provedor retornou uma versão anterior.")
        except (ValueError, KeyError, IndexError, TypeError, OverflowError) as exc:
            event = self.archive / "quarantine" / interval / (now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + digest)
            event.mkdir(parents=True)
            (event / "response.json.gz").write_bytes(gzip.compress(payload))
            meta = dict(source=SOURCE, symbol=SYMBOL, interval=interval, received=now.isoformat(),
                        sha256=digest, reason=str(exc))
            (event / "rejection.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf8")
            raise
        if digest != previous.get("sha256"):
            directory = self.archive / interval
            directory.mkdir(parents=True, exist_ok=True)
            dest = directory / (now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + digest + ".json.gz")
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as tmp:
                try:
                    tmp.write(gzip.compress(payload))
                    tmp.close()
                    os.replace(tmp.name, dest)
                finally:
                    Path(tmp.name).unlink(missing_ok=True)
        return dict(value=value, source=SOURCE, sha256=digest, received=now.isoformat())

    def snapshot(self):
        with self.lock:
            for interval, seconds in (("1m", 60), ("1d", 900)):
                if time.monotonic() < self.next.get(interval, 0):
                    continue
                try:
                    self.state[interval] = self.refresh(interval)
                    self.state[interval]["error"] = False
                except (OSError, ValueError, KeyError, IndexError, TypeError, OverflowError) as exc:
                    logging.warning("PETR4 %s: %s", interval, exc)
                    self.state.setdefault(interval, {})["error"] = True
                self.state[interval]["checked"] = datetime.now(timezone.utc).isoformat()
                self.next[interval] = time.monotonic() + seconds
            now = pd.Timestamp.now(tz="UTC")
            quote = self.state["1m"].get("value")
            age = (now - pd.Timestamp(quote["time"])).total_seconds() if quote else None
            return json.loads(json.dumps(dict(quote=self.state["1m"], daily=self.state["1d"],
                session=session_info(now), today=str(now.tz_convert(ZONE).date()), age_seconds=age)))
