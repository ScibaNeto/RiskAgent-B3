import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import painel


class AssetViewTests(unittest.TestCase):
    def test_past_peak_gap_and_forecast_alignment(self):
        dates = pd.to_datetime(["2026-11-16", "2026-11-17", "2026-11-19"])
        series = {"PETR4": pd.Series([100, 80, 200], index=dates),
                  "IBOV": pd.Series([10, 11, 12], index=dates)}
        manifest = {"assets": [{"asset": key} for key in series]}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            pd.DataFrame([{"date": "2026-11-17", "asset": "PETR4", "model": "GJR-GARCH t",
                           "var_pct": -7, "return_pct": -20}]).to_csv(run / "phase2_forecasts.csv", index=False)
            with patch.object(painel, "snapshot_prices", side_effect=lambda _, e: series[e["asset"]]):
                rows = painel.asset_history(run, manifest)
        self.assertEqual(rows[1]["drawdown"], -20)
        self.assertEqual(rows[1]["var_pct"], -7)
        self.assertEqual(rows[2]["date"], "2026-11-18")
        self.assertIsNone(rows[2]["PETR4"])
        self.assertIsNone(rows[2]["return_pct"])
        self.assertEqual(rows[3]["drawdown"], 0)
