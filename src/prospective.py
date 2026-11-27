"""Livro de previsões experimentais. Uma emissão e uma primeira apuração por origem."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from filelock import FileLock

from .b3_sessions import _schedule, session_prices
from .known_prices import snapshot_prices
from .market_data import write_json
from .prediction import HORIZONS, design, examples, fit_fold


def maintain(root, history, run, now=None):
    realtime = now is None
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now).tz_convert("UTC")
    root.mkdir(parents=True, exist_ok=True)
    prices = pd.Series({pd.Timestamp(r["date"]):r["PETR4"] for r in history},dtype=float)
    prices = session_prices(prices)
    origin = prices.index[-1]
    schedule = _schedule(origin.year, max(origin.year, now.year)+1)
    completed = schedule.index[schedule.close <= now]
    with FileLock(str(root/".lock"), timeout=60):
        for path in sorted(root.glob("*/forecast.json")):
            old = json.loads(path.read_text(encoding="utf8"))
            for item in old["forecasts"]:
                date = pd.Timestamp(item["target"])
                output = path.parent/f"realized-{item['horizon']}.json"
                if output.exists() or date not in completed or date > prices.index[-1]:
                    continue
                sample = prices.loc[old["origin"]:date]
                if sample.size != item["horizon"]+1 or not np.isfinite(sample).all() or (sample<=0).any():
                    continue
                ret = float(100*(sample.iloc[-1]/sample.iloc[0]-1))
                write_json(output, dict(known_at=now.isoformat(),run=run,actual_pct=ret,up=int(ret>0),
                           forecast_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           brier=(item["model"]-int(ret>0))**2,baseline_brier=(item["baseline"]-int(ret>0))**2))
        path = root/str(origin.date())/"forecast.json"
        if path.exists() or completed.empty or origin != completed[-1]:
            return
        _, features = design(history)
        test = features.tail(1)
        if test.isna().any().any():
            return
        future = schedule.loc[schedule.index>origin]
        rows = []
        for horizon in HORIZONS:
            target = future.iloc[horizon-1]
            data = examples(history,horizon)
            fit = fit_fold(data.loc[data.target < origin],test)
            if fit is None:
                return
            values, split = fit
            row = values.iloc[0]
            rows.append(dict(horizon=horizon,target=str(target.name.date()),**split,
                             **{k:float(row[k]) for k in ["model","baseline","point","q10","q90","base_point","base_q10","base_q90"]}))
        issued = pd.Timestamp.now(tz="UTC") if realtime else now
        if issued >= future.iloc[0].close:
            return
        path.parent.mkdir(exist_ok=True)
        write_json(path,dict(origin=str(origin.date()),issued=issued.isoformat(),run=run,
                   after_next_open=bool(issued>=future.iloc[0].open),forecasts=rows))


def report(root):
    paths = sorted(root.glob("*/forecast.json"))
    if not paths:
        return None
    latest = json.loads(paths[-1].read_text(encoding="utf8"))
    latest["outcomes"] = []
    for origin in reversed(paths):
        for item in json.loads(origin.read_text(encoding="utf8"))["forecasts"]:
            outcome=origin.parent/f"realized-{item['horizon']}.json"
            if outcome.is_file():
                latest["outcomes"].append(dict(origin=origin.parent.name,target=item["target"],
                    horizon=item["horizon"],model=item["model"],point=item["point"],
                    **json.loads(outcome.read_text(encoding="utf8"))))
    latest["settled"] = sum(1 for p in paths for _ in p.parent.glob("realized-*.json"))
    latest["total"] = sum(len(json.loads(p.read_text(encoding="utf8"))["forecasts"]) for p in paths)
    return latest


def update():
    root=Path(__file__).resolve().parents[1]
    for manifest in sorted((root/"outputs/phase2_1/runs").glob("*/manifest.json"), reverse=True):
        if (manifest.parent/"phase2_report.md").exists():
            break
    else:
        raise ValueError("Nenhuma execução de risco completa.")
    metadata=json.loads(manifest.read_text(encoding="utf8"))
    frame=session_prices(pd.concat({a["asset"]:snapshot_prices(manifest.parent,a) for a in metadata["assets"]
                                    if a["asset"] in {"PETR4","IBOV"}},axis=1))
    frame["date"]=frame.index.strftime("%Y-%m-%d")
    maintain(root/"outputs/prediction",frame.to_dict("records"),manifest.parent.name)


if __name__=="__main__":
    update()