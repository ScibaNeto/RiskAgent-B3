import io
import unittest

import numpy as np
import pandas as pd

from src.b3_sessions import session_prices
from src.prediction import evaluate, examples, scores


def fixture():
    index = session_prices(pd.Series([1, 2], index=pd.to_datetime(["2016-01-04", "2022-12-29"]))).index
    rng = np.random.default_rng(91)
    prices = np.exp(np.cumsum(rng.normal(0, .011, (len(index), 2)), axis=0))*40
    return pd.DataFrame(prices, columns=["PETR4", "IBOV"]).assign(date=index).to_dict("records")


class PredictionTests(unittest.TestCase):
    def test_target_uses_next_session_and_drops_missing(self):
        rows = fixture()[:110]
        rows[56]["PETR4"] = None
        rows[91]["PETR4"] = rows[90]["PETR4"]
        data = examples(rows)
        self.assertNotIn(rows[55]["date"], data.index)
        self.assertNotIn(rows[56]["date"], data.index)
        self.assertEqual(data.loc[rows[90]["date"], "up"], 0.)
        self.assertEqual(data.loc[rows[90]["date"], "target"], rows[91]["date"])
        self.assertNotIn(rows[-1]["date"], data.index)

    def test_future_prices_do_not_change_previous_fold_forecasts(self):
        rows = fixture()
        def run(rows):
            csv = io.StringIO()
            result = evaluate(rows, predictions_csv=csv)
            csv.seek(0)
            return result, pd.read_csv(csv)
        result, original = run(rows)
        for row in rows:
            if row["date"].year == 2022:
                row["PETR4"] *= 1.2
        _, changed = run(rows)
        early = original.origin < "2022-01-01"
        np.testing.assert_allclose(original.model[early], changed.model[early])
        for f in result["folds"]:
            self.assertLess(f["train_to"], f["cal_from"])
            self.assertLess(f["cal_to"], f["test_from"])
        self.assertEqual(sum(b["n"] for b in result["calibration"]["model"]), len(original))
        self.assertEqual(evaluate(rows[:100]), None)

    def test_reference_scores(self):
        result=scores(np.array([1.,0.]),np.array([.5,.5]))
        self.assertEqual(result["brier"], .25)
        self.assertAlmostEqual(result["log_loss"], np.log(2))