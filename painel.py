"""Gera e abre o painel de risco da execução local mais recente."""
import argparse
import csv
import json
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


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
            "coverage": manifest["coverage_status"]}
    if not data["tail"] or not data["stress"]:
        raise ValueError(f"A execução {run.name} tem tabelas vazias.")
    template = (ROOT / "src" / "painel.html").read_text(encoding="utf8")
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
