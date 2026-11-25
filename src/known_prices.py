"""Preços aceitos em snapshots que já existiam no instante consultado."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

if __package__:
    from .market_data import clean_prices
else:
    from market_data import clean_prices


def get_observations(asset: str, as_of: str, outputs: Path) -> tuple[pd.Series, dict]:
    cutoff = pd.Timestamp(as_of)
    if pd.isna(cutoff) or cutoff.tz is None:
        raise ValueError("Informe um instante com fuso horário.")
    candidates = []
    for phase in ("phase1", "phase2_1"):
        for path in (outputs / phase / "runs").glob("*/manifest.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if manifest.get("schema_version") != 2:
                continue
            known = pd.Timestamp(manifest["created_at_utc"])
            if known > cutoff:
                continue
            for entry in manifest["assets"]:
                if (entry["asset"] == asset and entry["validation"]["status"] == "passed"
                        and entry["quality"].get("snapshot")):
                    candidates.append((known, path, entry))
    if not candidates:
        raise LookupError("Histórico de versões indisponível para esse ativo e corte.")
    latest = max(item[0] for item in candidates)
    matching = [item for item in candidates if item[0] == latest]
    if len({item[2]["sha256"] for item in matching}) > 1:
        raise ValueError("Versões conflitantes no mesmo instante.")
    known, path, entry = max(matching, key=lambda item: str(item[1]))
    prices = snapshot_prices(path.parent, entry)
    root = path.parent
    return prices, {"dataset_version": entry["sha256"], "last_observation": entry["end_date"],
                    "freshness_at_run": entry["quality"].get("freshness", "unknown"), "asset": asset, "known_at": known.isoformat(), "run_id": root.name,
                    "sha256": entry["sha256"], "source": entry["provider"]}


def snapshot_prices(run: Path, entry: dict) -> pd.Series:
    """Reproduz uma entrada verificada da execução indicada."""
    root = run.resolve()
    asset = entry["asset"]
    snapshot = (root / entry["quality"]["snapshot"]).resolve()
    if not snapshot.is_relative_to(root):
        raise ValueError("Snapshot fora da execução.")
    payload = snapshot.read_bytes()
    if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
        raise ValueError("Hash do snapshot divergente.")
    frame = pd.read_csv(io.BytesIO(payload), index_col=0, dtype=str)
    column = next((c for c in ("Close", "Adj Close", "price", asset) if c in frame), frame.columns[0])
    prices, _ = clean_prices(frame[column], asset, pd.Timestamp(entry["end_date"]))
    prices = prices.loc[entry["start_date"]:entry["end_date"]]
    prices = prices.drop(pd.to_datetime(entry["quality"]["excluded_dates"]), errors="ignore")
    if len(prices) != entry["price_count"]:
        raise ValueError("Contagem de preços divergente do manifesto.")
    return prices


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset")
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    try:
        series, origin = get_observations(args.asset, args.as_of, Path(__file__).resolve().parents[1] / "outputs")
    except (LookupError, ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(origin, ensure_ascii=False))
    print(series.tail().to_string())
