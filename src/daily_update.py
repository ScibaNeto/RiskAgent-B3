"""Atualização incremental após o fechamento. Use --watch para manter a rotina local ativa."""
import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from filelock import FileLock

if __package__:
    from .data_manifest import file_sha256
    from .b3_sessions import completed_sessions
else:
    from data_manifest import file_sha256
    from b3_sessions import completed_sessions

ROOT = Path(__file__).resolve().parents[1]


def already_current(runs: Path, session: str) -> bool:
    for quality in sorted(runs.glob("*/data_quality.json"), reverse=True):
        if not (quality.parent / "phase2_report.md").is_file():
            continue
        root = quality.parent.resolve()
        try:
            records = json.loads(quality.read_text("utf-8"))["assets"]
            if set(records) != {"PETR4", "VALE3", "IBOV"}:
                return False
            for record in records.values():
                if record["last_completed_session"] != session or record["stale_sessions"] != 0:
                    return False
                snapshot = (root / record["snapshot"]).resolve()
                if not snapshot.is_relative_to(root) or not snapshot.is_file():
                    return False
                if file_sha256(snapshot) != record["sha256"]:
                    return False
        except (OSError, KeyError, TypeError, ValueError) as exc:
            logging.warning("Relatório de qualidade inutilizável em %s: %s", root, exc)
            return False
        return True
    return False


def update() -> None:
    runs = ROOT / "outputs" / "phase2_1" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with FileLock(str(runs / ".daily.lock"), timeout=60):
        now = pd.Timestamp.now(tz="UTC")
        start = (now - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        session = str(completed_sessions(start, now)[-1].date())
        if __package__:
            from .market_context import refresh
        else:
            from market_context import refresh
        refresh()
        if already_current(runs, session):
            print(f"Pregão {session} já atualizado.", flush=True)
            return
        subprocess.run([sys.executable, str(ROOT / "src" / "phase2_risk_engine_v2.py"),
                        "--strict-cache", "--max-stale-sessions", "0"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    if args.watch:
        while True:
            try:
                update()
            except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                logging.error("Atualização falhou. Nova tentativa em 30 minutos. %s", exc)
            time.sleep(1800)
    else:
        update()
