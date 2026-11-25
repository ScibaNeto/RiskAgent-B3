"""Helpers for reproducible manifests of local financial data runs."""
from __future__ import annotations

import sys
import hashlib
import json
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def write_data_manifest(
    path: Path,
    *,
    run_id: str,
    assets: dict[str, str],
    prices: dict[str, pd.Series],
    returns: dict[str, pd.Series],
    data_directory: Path,
    sources: dict[str, str],
    settings: dict[str, Any],
    collected_at_utc: str | None = None,
    input_records: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Write a compact manifest with provenance and final-series checks."""
    if __package__:
        from .market_data import write_json
    else:
        from market_data import write_json
    asset_records: list[dict[str, Any]] = []
    for asset, ticker in assets.items():
        price = prices[asset]
        ret = returns[asset]
        record = (input_records or {}).get(asset, {})
        price_file = path.parent / record["snapshot"] if "snapshot" in record else data_directory / f"{asset}.csv"
        numeric_prices = pd.to_numeric(price, errors="coerce")
        numeric_returns = pd.to_numeric(ret, errors="coerce")
        price_values = numeric_prices.to_numpy(dtype=float)
        return_values = numeric_returns.to_numpy(dtype=float)
        duplicates = int(price.index.duplicated().sum())
        ordered = bool(price.index.is_monotonic_increasing)
        nonfinite_returns = int((~np.isfinite(return_values)).sum())
        validation_passed = (
            len(price) >= 2
            and len(ret) > 0
            and np.isfinite(price_values).all()
            and (price_values > 0).all()
            and duplicates == 0
            and ordered
            and nonfinite_returns == 0
        )
        actual_hash = _file_sha256(price_file)
        if "sha256" in record and actual_hash != record["sha256"]:
            raise ValueError(f"Snapshot divergente para {asset}.")
        asset_records.append({
            "asset": asset,
            "ticker": ticker,
            "provider": "Yahoo Finance",
            "source_mode": sources.get(asset, "unknown"),
            "start_date": str(price.index.min().date()),
            "end_date": str(price.index.max().date()),
            "price_count": int(len(price)),
            "return_count": int(len(ret)),
            "collected_at_utc": record.get("collected_at_utc", collected_at_utc),
            "last_observation": str(price.index.max().date()),
            "price_type": "Close ajustado; auto_adjust=True",
            "adjustment_convention": "Yahoo Finance ajusta Close para eventos corporativos",
            "local_file": str(price_file),
            "sha256": actual_hash,
            "quality": record,
            "validation": {
                "status": "passed" if validation_passed else "failed",
                "null_prices": int(numeric_prices.isna().sum()),
                "nonpositive_prices": int((numeric_prices <= 0).sum()),
                "duplicate_dates": duplicates,
                "dates_ordered": ordered,
                "nonfinite_returns": nonfinite_returns,
                "returns_abs_over_15pct": int((numeric_returns.abs() > 15.0).sum()),
            },
        })

    manifest = {
        "schema_version": 2,
        "python_version": sys.version.split()[0],
        "source_sha256": {p.name: _file_sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "run_id": run_id,
        "coverage_status": (
            "partial" if any(r["quality"].get("coverage_status") == "partial" for r in asset_records)
            else "complete" if input_records else "unknown"
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": settings,
        "libraries": {
            name: _package_version(name)
            for name in ("pandas", "numpy", "scipy", "arch", "yfinance", "matplotlib", "exchange-calendars", "filelock")
        },
        "assets": asset_records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    common_dates = None
    for ret in returns.values():
        common_dates = ret.index if common_dates is None else common_dates.intersection(ret.index)
    common_dates = sorted(common_dates) if common_dates is not None else []
    quality = {"run_id": run_id, "common_return_dates": len(common_dates),
               "first_common": str(common_dates[0].date()) if common_dates else None,
               "last_common": str(common_dates[-1].date()) if common_dates else None,
               "assets": {asset: dict(record, outside_common=len(returns[asset]) - len(common_dates))
                          for asset, record in (input_records or {}).items()}}
    write_json(path.parent / "data_quality.json", quality)
    write_json(path, manifest)
    return manifest
