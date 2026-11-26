import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy.stats import t

from src import phase2_risk_engine_v2 as engine
from src.factor_stress import factor_stress


class StageTwoAcceptance(unittest.TestCase):
    def test_same_dates_past_window_and_student_scale(self):
        days = pd.date_range("2024-01-02", periods=8)
        r = pd.Series([-4., -2., 1., 2., 20., 0., -1., 4.], index=days)
        q = t.ppf(.01, 7) * np.sqrt(5/7)
        baseline = pd.DataFrame(dict(date=days, model="GJR-GARCH t", asset="A", var_pct=2*q))
        baseline.loc[5, "var_pct"] = np.nan
        blocks = pd.DataFrame([dict(asset="A", status="ok", forecast_start=str(days[4].date()),
                                    forecast_end=str(days[-1].date()), nu=7.)])
        with patch.object(engine, "WINDOW", 4):
            curves, summary = engine.compare_levels({"A": r}, baseline, blocks)
        self.assertEqual(len(summary), 9)
        self.assertTrue((summary.n == 3).all())
        at_start = curves.loc[curves.date == days[4]].set_index(["model", "alpha"])
        for a in [.05, .025, .01]:
            self.assertAlmostEqual(at_start.loc[("GJR-GARCH t", a), "var_pct"], 2*t.ppf(a, 7)*np.sqrt(5/7))
            self.assertAlmostEqual(at_start.loc[("Simulacao historica", a), "var_pct"], np.quantile(r.iloc[:4], a))
        self.assertFalse((curves.date == days[5]).any())

    def test_known_exposures_and_collinearity(self):
        days = pd.date_range("2023-01-02", periods=100, freq="B")
        x = pd.Series(np.sin(np.arange(100)), index=days)
        y = pd.Series(np.cos(np.arange(100)), index=days)
        log = lambda simple: 100*np.log1p(simple/100)
        data = {"A": log(.1+2*x+y), "B": log(.3+x-y), "IBOV": log(x)}
        result = factor_stress(data, {"A": .5, "B": .5}, log(y))
        both = result.query("market_shock_pct == -5 and fx_shock_pct == 5")
        np.testing.assert_allclose(both.portfolio_impact_pct, -7.5)
        with self.assertRaises(ValueError):
            factor_stress(data, {"A": .5, "B": .5}, log(x))