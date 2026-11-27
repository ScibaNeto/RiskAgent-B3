import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import prospective
from src.prediction import evaluate, examples
from src.b3_sessions import _schedule


class HorizonsTests(unittest.TestCase):
    def setUp(self):
        self.sessions = _schedule(2016, 2024)
        dates = self.sessions.loc["2016":"2023"].index
        rng = np.random.default_rng(12)
        p = 50*np.exp(np.cumsum(rng.normal(0,.01,(len(dates),2)),axis=0))
        self.rows = [dict(date=str(d.date()),PETR4=a,IBOV=b) for d,(a,b) in zip(dates,p)]

    def test_horizon_return_quantiles_purge_and_gap(self):
        h=60
        rows=self.rows
        rows[122]["PETR4"]=None
        d=examples(rows,h)
        self.assertNotIn(pd.Timestamp(rows[100]["date"]),d.index)
        day=pd.Timestamp(rows[200]["date"])
        self.assertEqual(d.loc[day,"target"],pd.Timestamp(rows[260]["date"]))
        self.assertAlmostEqual(d.loc[day,"return_pct"],100*(rows[260]["PETR4"]/rows[200]["PETR4"]-1))
        tested=evaluate(rows,horizon=h)
        for fold in tested["folds"]:
            self.assertLess(fold["train_to"],fold["cal_from"])
            self.assertLess(fold["cal_to"],fold["test_from"])
        self.assertTrue(0<=tested["returns"]["coverage"]<=1)

    def test_ledger_issue_before_target_replay_maturity_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rows=self.rows
            start=len(rows)-80
            now=self.sessions.loc[rows[start]["date"],"close"]+pd.Timedelta(minutes=5)
            prospective.maintain(root,rows[:start+1],"a",now)
            path,=list(root.glob("*/forecast.json"))
            initial=path.read_bytes()
            forecast=json.loads(initial)
            for item in forecast["forecasts"]:
                self.assertEqual(item["target"],rows[start+item["horizon"]]["date"])
                self.assertLessEqual(item["q10"],item["q90"])
            prospective.maintain(root,rows[:start+1],"revision",now)
            self.assertEqual(path.read_bytes(),initial)
            later=self.sessions.loc[rows[start+1]["date"],"close"]+pd.Timedelta(seconds=1)
            prospective.maintain(root,rows[:start+1],"stale",later)
            self.assertEqual(len(list(root.glob("*/forecast.json"))),1)
            prospective.maintain(root,rows[:start+2],"b",later)
            outcome=json.loads((path.parent/"realized-1.json").read_text())
            self.assertEqual(outcome["forecast_sha256"],hashlib.sha256(initial).hexdigest())
            self.assertFalse((path.parent/"realized-5.json").exists())
            self.assertEqual(prospective.report(root)["settled"],1)