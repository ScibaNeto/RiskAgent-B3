import unittest

import pandas as pd

from src.b3_sessions import completed_sessions
from src.opportunity import scan


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.cutoff=pd.Timestamp("2026-11-27T19:50Z")
        dates=completed_sessions("2026-09-01",self.cutoff)[-21:]
        self.data={"run":"run","history":[dict(date=str(day.date()),PETR4=100+i,VALE3=200-i,IBOV=100+i/2)
                                         for i,day in enumerate(dates)]}
        self.quality={k:dict(freshness="atualizado",stale_sessions=0,completeness="incompleto")
                      for k in ("PETR4","IBOV","VALE3")}
        self.day=self.data["history"][-1]["date"]
        self.risks={k:dict(date=self.day,var_pct=-3.,return_pct=-1.) for k in ("PETR4","VALE3")}

    def run_scan(self):
        return scan(self.data,self.quality,self.risks,self.cutoff)

    def test_candidate_and_relative_underperformance(self):
        out=self.run_scan()
        self.assertEqual(out["candidates"],["PETR4"])
        self.data["history"][-1]["IBOV"]=150
        self.assertEqual(self.run_scan()["cards"][0]["status"],"Sinais conflitantes")

    def test_missing_stale_and_breach(self):
        self.risks["PETR4"]["return_pct"]=-5
        self.assertEqual(self.run_scan()["cards"][0]["status"],"Sinais conflitantes")
        self.quality["IBOV"]["freshness"]="desatualizado"
        self.assertEqual(self.run_scan()["candidates"],[])
        self.data["history"][3]["VALE3"]=None
        self.risks.clear()
        self.assertEqual([c["status"] for c in self.run_scan()["cards"]],["Dados insuficientes"]*2)
        self.data["history"]=[]
        self.assertEqual(self.run_scan()["candidates"],[])

    def test_only_prediction_known_at_cut_and_matching_run(self):
        f=dict(origin=self.day,run="run",issued="2026-11-27T19:00Z",forecasts=[dict(model=.30,horizon=1)])
        self.data["prospective"]=f
        self.assertEqual(self.run_scan()["cards"][0]["status"],"Sinais conflitantes")
        for key,value in [("run","different"),("issued","2026-11-27T20:00Z"),("origin","2026-11-25")]:
            self.data["prospective"]=dict(f,**{key:value})
            self.assertEqual(self.run_scan()["candidates"],["PETR4"])
        self.cutoff+=pd.Timedelta(days=1)
        self.assertEqual(self.run_scan()["cards"][0]["status"],"Dados insuficientes")