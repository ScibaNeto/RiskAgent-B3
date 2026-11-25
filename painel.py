"""Gera e abre o painel de risco da execução local mais recente."""
import argparse
import csv
import json
import webbrowser
from pathlib import Path

import pandas as pd
from src.b3_sessions import session_prices
from src.known_prices import snapshot_prices

ROOT = Path(__file__).resolve().parent


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def asset_history(run, manifest):
    entries = {entry["asset"]: entry for entry in manifest["assets"]}
    if not {"PETR4", "IBOV"} <= entries.keys() or not (run / "phase2_forecasts.csv").exists():
        return []
    prices = pd.concat({key: snapshot_prices(run, entries[key]) for key in ("PETR4", "IBOV")}, axis=1)
    frame = session_prices(prices)
    frame["drawdown"] = 100 * (frame.PETR4 / frame.PETR4.cummax() - 1)
    forecasts = pd.read_csv(run / "phase2_forecasts.csv", parse_dates=["date"])
    model = forecasts.loc[(forecasts.asset == "PETR4") & (forecasts.model == "GJR-GARCH t")].set_index("date")
    frame = frame.join(model[["return_pct", "var_pct"]], validate="one_to_one")
    frame.insert(0, "date", frame.index.strftime("%Y-%m-%d"))
    return json.loads(frame.to_json(orient="records", date_format="iso", double_precision=10))


def build(runs, output):
    required = ["manifest.json", "phase2_2_tail.csv", "phase2_3_stress.csv", "phase2_report.md"]
    for run in sorted(runs.glob("run_*"), reverse=True):
        if all((run / name).is_file() for name in required):
            break
    else:
        raise ValueError("Gere uma execução com python src/phase2_risk_engine_v2.py e abra o painel novamente.")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf8"))
    data = {"run": run.name, "created": manifest["created_at_utc"],
            "tail": read_rows(run / required[1]), "stress": read_rows(run / required[2]),
            "history": asset_history(run, manifest), "coverage": manifest["coverage_status"]}
    if not data["tail"] or not data["stress"]:
        raise ValueError(f"A execução {run.name} tem tabelas vazias.")
    template = (ROOT / "src" / "painel.html").read_text(encoding="utf8")
    template = template.replace("/*ASSET_VIEW*/", (ROOT / "src" / "asset_view.js").read_text(encoding="utf8"))
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace("/*RUN_DATA*/", payload), encoding="utf8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sem-abrir", action="store_true")
    args = parser.parse_args()
    try:
        path = build(ROOT / "outputs/phase2_1/runs", ROOT / "outputs/painel/index.html")
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")
    print(path)
    if not args.sem_abrir:
        webbrowser.open(path.as_uri())
