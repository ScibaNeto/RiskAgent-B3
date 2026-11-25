import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from risk_extensions import es_inference, hac_standard_error, portfolio_scenarios, tail_summary
from b3_sessions import completed_sessions


class RiskExtensionsTests(unittest.TestCase):
    def test_expected_es_moment_and_interval(self):
        data = pd.DataFrame({"return_pct": [-4, 0, 0, 0], "var_pct": -2, "es_pct": -4})
        result = tail_summary(data, 0.25)
        self.assertEqual(result["es_unconditional_z2"], 0)
        self.assertLess(result["hit_rate_ci_low"], 0.25)
        self.assertGreater(result["hit_rate_ci_high"], 0.25)

    def test_portfolio_shocks_use_simple_returns_on_common_date(self):
        idx = pd.to_datetime(["2026-11-23", "2026-11-24"])
        a = pd.Series(100 * np.log([0.5, 0.9]), index=idx)
        b = pd.Series([0.0], index=idx[1:])
        rows = portfolio_scenarios({"A": a, "B": b}, {"A": 0.4, "B": 0.6})
        self.assertEqual(rows.iloc[0]["date"], "2026-11-24")
        np.testing.assert_allclose(rows.portfolio_simple_pct, [-4, -4, -6])

    def test_hac_matches_bartlett_matrix_with_gap(self):
        x = pd.Series([2., 0., np.nan, 3., 1.])
        centered = np.array([0.5, -1.5, 1.5, -0.5])
        kernel = np.eye(4)
        kernel[0, 1] = kernel[1, 0] = kernel[2, 3] = kernel[3, 2] = 2/3
        expected = np.sqrt(centered @ kernel @ centered) / 4
        self.assertAlmostEqual(hac_standard_error(x, 2), expected)

    def test_es_inference_direction_and_sparse_tail(self):
        dates = completed_sessions("2020-01-01", pd.Timestamp("2022-01-01", tz="UTC"))[:250]
        frame = pd.DataFrame({"date": dates, "return_pct": np.tile([-8.] + [0.]*9, 25),
                              "var_pct": -2., "es_pct": -4.})
        self.assertLess(es_inference(frame, 0.1)["es_p_lower"], 0.05)
        frame["es_pct"] = -8.
        self.assertAlmostEqual(es_inference(frame, 0.1)["es_p_lower"], 0.5)
        frame["return_pct"] = 0.
        self.assertTrue(np.isnan(es_inference(frame, 0.1)["es_p_lower"]))

    def test_joint_shocks_and_incomplete_input(self):
        series = pd.Series([0.], index=pd.to_datetime(["2026-11-23"]))
        returns, weights = {"A":series, "B":series}, {"A":0.7, "B":0.3}
        rows = portfolio_scenarios(returns, weights, {"divergente":{"A":-20, "B":10}})
        self.assertEqual(rows.iloc[-1].portfolio_simple_pct, -11)
        with self.assertRaises(ValueError):
            portfolio_scenarios(returns, weights, {"incompleto":{"A":-20}})
