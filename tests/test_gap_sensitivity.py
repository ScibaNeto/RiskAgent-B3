import json
import unittest

import numpy as np
import pandas as pd
from scipy.stats import t

from src.gap_sensitivity import expected_gap_var, gap_sensitivity


class GapSensitivityTests(unittest.TestCase):
    def test_two_unobserved_shocks(self):
        params = {"nu": 8, "omega": .4, "alpha[1]": .1, "gamma[1]": .2, "beta[1]": .6}
        q = t.ppf(.01, 8) * np.sqrt(6 / 8)
        self.assertAlmostEqual(expected_gap_var(2*q, params, .01, 2), q*np.sqrt(.4+.8*(.4+.8*4)))

    def test_weekend_gap_missing_forecast_and_future_fit(self):
        dates = ["2024-03-01", "2024-03-04", "2024-03-06"]
        data = pd.DataFrame(dict(date=dates, model="EWMA normal", asset="A", return_pct=1, var_pct=-2))
        future = pd.DataFrame([dict(asset="A", status="ok", fit_end=dates[-1], forecast_start=dates[-1],
                                    forecast_end=dates[-1], parameters_json=json.dumps({}))])
        report = gap_sensitivity(data, future, .01)
        self.assertEqual(report.date.tolist(), [dates[-1]])
        self.assertEqual(report.missing_sessions.tolist(), [1])
        self.assertEqual(report.expected_variance_var_pct.tolist(), [-2])
        data["model"] = "GJR-GARCH t"
        self.assertEqual(gap_sensitivity(data, future, .01).status.tolist(), ["ajuste_indisponivel"])
        data.loc[2, "var_pct"] = np.nan
        self.assertEqual(gap_sensitivity(data, future, .01).status.tolist(), ["previsao_indisponivel"])
