import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from b3_sessions import completed_sessions, daily_log_returns
from data_manifest import write_data_manifest
from market_data import atomic_bytes, clean_prices, ingest
from phase2_risk_engine_v2 import build_portfolio_log_returns


def quotes(dates, values):
    return pd.Series(values, index=pd.to_datetime(dates), name="A", dtype=float)


class CalendarTests(unittest.TestCase):
    def test_holiday_weekend_and_intraday_cutoff(self):
        # Quinta 19, sexta feriado, segunda 23: antes do fechamento, 19 ainda é o último.
        for cutoff in ("2026-11-20 23:00Z", "2026-11-22 23:00Z", "2026-11-23 15:00Z"):
            with self.subTest(cutoff=cutoff):
                days = completed_sessions("2026-11-16", pd.Timestamp(cutoff))
                self.assertEqual(days[-1], pd.Timestamp("2026-11-19"))
        days = completed_sessions("2026-11-16", pd.Timestamp("2026-11-23 23:00Z"))
        self.assertEqual(days[-1], pd.Timestamp("2026-11-23"))

    def test_november_2020_exception_and_july_2026_session(self):
        for date in ("2020-11-20", "2026-07-09"):
            days = completed_sessions(date, pd.Timestamp(f"{date} 23:00Z"))
            self.assertEqual(days.tolist(), [pd.Timestamp(date)])

    def test_missing_close_and_next_return_excluded_for_asset_and_portfolio(self):
        dates = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-23"]
        full = quotes(dates, [100, 101, 110, 121, 132])
        gap = full.drop(pd.Timestamp("2026-11-17"))
        expected = pd.to_datetime(["2026-11-19", "2026-11-23"])
        ret = daily_log_returns(gap)
        self.assertEqual(ret.index.tolist(), expected.tolist())
        np.testing.assert_allclose(ret, 100 * np.log([121 / 110, 132 / 121]))
        portfolio = build_portfolio_log_returns({"A": full, "B": gap}, {"A": 0.5, "B": 0.5})
        pd.testing.assert_series_equal(portfolio, ret, check_names=False)

    def test_midnight_local_and_utc_representations_agree(self):
        local = pd.Timestamp("2026-11-19", tz="America/Sao_Paulo")
        for stamp in (local, local.tz_convert("UTC"), pd.Timestamp("2026-11-19", tz="UTC")):
            clean, checks = clean_prices(pd.Series([2.0], index=[stamp]), "A", pd.Timestamp("2026-11-23"))
            self.assertEqual(clean.index.tolist(), [pd.Timestamp("2026-11-19")])
            self.assertEqual(checks["invalid_rows"], 0)
        with self.assertRaises(ValueError):
            clean_prices(pd.Series([2.0], index=[local + pd.Timedelta(hours=14)]), "A", pd.Timestamp("2026-11-23"))


class IngestionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache = self.root / "raw" / "A.csv"
        self.cache.parent.mkdir()
        self.run = self.root / "run"
        self.prices = quotes(["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"], [100, 101, 102, 103])
        self.prices.to_frame("Close").to_csv(self.cache)
        self.original = self.cache.read_bytes()
        self.fetch = Mock(side_effect=AssertionError("consulta inesperada ao provedor"))

    def load(self, **kwargs):
        options = dict(cache_path=self.cache, start="2026-11-16", minimum=2, overlap_days=5,
                       fetch=self.fetch, run_dir=self.run, as_of=pd.Timestamp("2026-11-23 23:00Z"))
        return ingest("A", **(options | kwargs))

    def test_offline_snapshot_and_manifest_survive_cache_change(self):
        result = self.load(offline=True, strict=True, max_stale_sessions=1)
        self.fetch.assert_not_called()
        self.assertEqual(result.record["stale_sessions"], 1)
        self.assertIsNone(result.record["collected_at_utc"])
        self.cache.write_bytes(b"changed")
        manifest = write_data_manifest(
            self.run / "manifest.json", run_id="test", assets={"A": "A.SA"}, prices={"A": result.prices},
            returns={"A": result.returns}, sources={"A": result.record["source_mode"]}, data_directory=self.cache.parent,
            input_records={"A": result.record}, settings={})
        snapshot = Path(manifest["assets"][0]["local_file"])
        self.assertEqual(snapshot.read_bytes(), self.original)
        self.assertEqual(manifest["assets"][0]["sha256"], hashlib.sha256(self.original).hexdigest())
        self.assertIsNone(manifest["assets"][0]["collected_at_utc"])
        self.assertEqual(manifest["coverage_status"], "partial")

    def test_strict_rejected_candidate_preserves_exact_cache(self):
        revised = self.prices.copy()
        revised.iloc[-1] = 104
        with self.assertRaisesRegex(RuntimeError, "Modo estrito"):
            self.load(fetch=Mock(return_value=revised), strict=True, max_stale_sessions=0)
        self.assertEqual(self.cache.read_bytes(), self.original)
        failure = json.loads((self.run / "data_failure.json").read_text("utf-8"))
        self.assertEqual(failure["status"], "interrupted")
        self.assertIn("Modo estrito", failure["fallback_reason"])

    def test_missing_cache_offline_interrupts_before_creating_snapshot(self):
        self.cache.unlink()
        with self.assertRaisesRegex(RuntimeError, "Amostra insuficiente"):
            self.load(offline=True)
        self.fetch.assert_not_called()
        self.assertFalse(self.cache.exists())
        self.assertFalse((self.run / "inputs").exists())
        self.assertTrue((self.run / "data_failure.json").is_file())

    def test_invalid_partial_batch_is_rejected_despite_valid_cache(self):
        for bad in [np.nan, -1, np.inf]:
            with self.subTest(bad=bad):
                remote = quotes(["2026-11-19", "2026-11-23"], [123, bad])
                result = self.load(fetch=Mock(return_value=remote))
                self.assertEqual(result.record["source_mode"], "cache_fallback_download_invalid")
                self.assertIsNone(result.record["collected_at_utc"])
                self.assertEqual(self.cache.read_bytes(), self.original)

    def test_rejection_contains_original_adapter_rows_origin_time_hash_and_reason(self):
        batch = quotes(["2026-11-19", "2026-11-23"], [0, 123])
        result = self.load(fetch=Mock(return_value=batch), provider="fixture", symbol="A.SA")
        event = Path(result.record["quarantine"][0])
        meta = json.loads((event / "event.json").read_text("utf8"))
        payload = (event / "payload.csv").read_bytes()
        self.assertEqual(payload, batch.to_csv(lineterminator="\n", na_rep="NaN").encode())
        self.assertEqual(meta["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual((meta["source"], meta["symbol"]), ("fixture", "A.SA"))
        self.assertLessEqual(pd.Timestamp(meta["received_at_utc"]), pd.Timestamp(meta["rejected_at_utc"]))
        self.assertTrue(meta["reason"])
        self.assertEqual(self.cache.read_bytes(), self.original)
        self.assertEqual(result.record["provider_status"], "invalido")
        self.assertEqual(result.record["freshness"], "desatualizado")

    def test_quality_tracks_freshness_separately_from_historical_gaps(self):
        with_gap = self.prices.drop(self.prices.index[1])
        with_gap.loc[pd.Timestamp("2026-11-23")] = 106.0
        with_gap.to_csv(self.cache)
        data = self.load(offline=True)
        self.assertEqual((data.record["freshness"], data.record["completeness"]), ("atualizado", "incompleto"))

    def test_rejected_schema_and_missing_provider_have_distinct_status(self):
        invalid = self.load(fetch=Mock(return_value=self.prices.to_frame("Volume")))
        self.assertEqual(invalid.record["provider_status"], "invalido")
        self.assertIn("Volume", (Path(invalid.record["quarantine"][0]) / "payload.csv").read_text())
        unavailable = self.load(fetch=Mock(side_effect=TimeoutError("timeout")))
        self.assertEqual(unavailable.record["provider_status"], "indisponivel")
        self.assertEqual(unavailable.record["quarantine"], [])
        self.assertEqual(self.cache.read_bytes(), self.original)

    def test_manifest_aborts_if_archived_input_was_modified(self):
        data = self.load(offline=True)
        (self.run / data.record["snapshot"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Snapshot divergente"):
            write_data_manifest(self.run / "manifest.json", run_id="test", assets={"A":"A.SA"},
                                prices={"A": data.prices}, returns={"A": data.returns}, sources={},
                                data_directory=self.cache.parent, input_records={"A": data.record}, settings={})
        self.assertFalse((self.run / "manifest.json").exists())

    def test_daily_update_skips_only_complete_current_universe(self):
        from daily_update import already_current
        root = self.root / "runs" / "run_example"
        root.mkdir(parents=True)
        quality = root / "data_quality.json"
        assets = {a: {"last_completed_session":"2026-11-23", "stale_sessions":0}
                  for a in ("PETR4", "VALE3", "IBOV")}
        quality.write_text(json.dumps({"assets":assets}))
        self.assertFalse(already_current(root.parent, "2026-11-23"))
        (root / "phase2_report.md").touch()
        self.assertTrue(already_current(root.parent, "2026-11-23"))
        self.assertFalse(already_current(root.parent, "2026-11-24"))
        assets["PETR4"]["stale_sessions"] = 1
        quality.write_text(json.dumps({"assets":assets}))
        self.assertFalse(already_current(root.parent, "2026-11-23"))

    def test_cache_with_invalid_rows_interrupts_offline(self):
        self.cache.write_bytes(self.original + b"2026-11-23,inf\n")
        with self.assertRaisesRegex(RuntimeError, "Amostra insuficiente"):
            self.load(offline=True)
        self.assertIn("cache_error", json.loads((self.run / "data_failure.json").read_text("utf-8")))

    def test_partial_current_bar_omitted_from_written_cache(self):
        remote = quotes(["2026-11-19", "2026-11-23"], [103, 999])
        result = self.load(fetch=Mock(return_value=remote), as_of=pd.Timestamp("2026-11-23 15:00Z"),
                           strict=True, max_stale_sessions=0)
        self.assertEqual(result.record["stale_sessions"], 0)
        self.assertEqual(result.record["provider_attempts"][0]["excluded_dates"], ["2026-11-23"])
        self.assertNotIn(b"2026-11-23", self.cache.read_bytes())

    def test_adjustment_at_overlap_boundary_requires_consistent_full_history(self):
        remote = self.prices * 0.5
        remote.loc[pd.Timestamp("2026-11-23")] = 52
        fetch = Mock(side_effect=[remote.iloc[-3:], remote])
        result = self.load(fetch=fetch, overlap_days=1)
        self.assertEqual([c.args[0] for c in fetch.call_args_list], ["2026-11-18", "2026-11-16"])
        self.assertEqual(result.record["source_mode"], "yahoo_finance_full_history")
        self.assertIn("2026-11-18", result.record["overlap_revisions"])
        np.testing.assert_allclose(result.prices, remote)

    def test_incomplete_full_refresh_keeps_previous_cache(self):
        revised = self.prices.iloc[-2:] * 0.5
        result = self.load(fetch=Mock(side_effect=[revised, revised]))
        self.assertEqual(result.record["source_mode"], "cache_fallback_download_invalid")
        self.assertEqual(self.cache.read_bytes(), self.original)

    def test_transient_failure_and_retry(self):
        remote = quotes(["2026-11-19", "2026-11-23"], [103, 105])
        with patch("market_data.time.sleep") as sleep:
            result = self.load(fetch=Mock(side_effect=[TimeoutError("timeout"), remote]), attempts=2)
        sleep.assert_called_once_with(5)
        self.assertEqual(result.record["provider_attempts"][0]["error"], "timeout")
        self.assertEqual(result.record["stale_sessions"], 0)
        self.assertIsNotNone(result.record["collected_at_utc"])

    def test_online_and_snapshot_replay_are_bitwise_equal(self):
        remote = self.prices.copy()
        remote.iloc[-1] = np.nextafter(103.0, 104.0)
        remote.loc[pd.Timestamp("2026-11-23")] = np.nextafter(110.0, 109.0)
        online = self.load(fetch=Mock(return_value=remote))
        snapshot = self.run / online.record["snapshot"]
        replay = self.load(cache_path=snapshot, run_dir=self.root / "replay", offline=True)
        np.testing.assert_array_equal(online.prices, replay.prices)
        np.testing.assert_array_equal(online.returns, replay.returns)
        self.assertEqual(replay.record["sha256"], online.record["sha256"])
        self.assertEqual(replay.record["coverage_status"], "complete")

    def test_concurrent_writer_keeps_newer_cache(self):
        def competing_update(_):
            self.cache.write_bytes(b"concurrent version")
            return self.prices

        with self.assertRaisesRegex(RuntimeError, "outra execução"):
            self.load(fetch=competing_update)
        self.assertEqual(self.cache.read_bytes(), b"concurrent version")

    def test_failed_replace_leaves_no_partial_csv(self):
        with patch("market_data.os.replace", side_effect=OSError("disk error")):
            with self.assertRaisesRegex(OSError, "disk error"):
                atomic_bytes(self.cache, b"candidate")
        self.assertEqual(self.cache.read_bytes(), self.original)
        self.assertEqual(list(self.cache.parent.iterdir()), [self.cache])
