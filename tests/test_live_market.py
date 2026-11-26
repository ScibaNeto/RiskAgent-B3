import gzip
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.live_market import LiveMarket, parse_bars, quote_from, session_info, volume_from
from src.b3_sessions import completed_sessions


def payload(dates, interval="1m"):
    result = dict(meta=dict(symbol="PETR4.SA", currency="BRL", dataGranularity=interval),
                  timestamp=[int(i.timestamp()) for i in dates],
                  indicators=dict(quote=[dict(close=[40.] * len(dates), volume=list(range(len(dates))))]))
    return json.dumps(dict(chart=dict(error=None, result=[result]))).encode()


class MarketPageTests(unittest.TestCase):
    def test_point_in_time_and_regular_hours(self):
        times = pd.date_range("2024-03-04T14:00Z", periods=3, freq="min")
        now = times[-1] + pd.Timedelta(seconds=30)
        bars = parse_bars(payload(times), "1m", now)
        self.assertEqual(quote_from(bars, now)["time"], times[-2].isoformat())
        self.assertEqual(session_info(now), "Pregão em andamento")
        self.assertEqual(session_info(now-pd.Timedelta(days=1)), "Sem pregão hoje")
        with self.assertRaises(ValueError):
            parse_bars(payload(times), "1m", times[0])
        with self.assertRaises(ValueError):
            parse_bars(payload(times), "1d", now)

    def test_volume_uses_exact_prior_sessions(self):
        now = pd.Timestamp("2024-04-22T23:00Z")
        days = completed_sessions("2024-02-01", now)[-21:].tz_localize("UTC") + pd.Timedelta(hours=13)
        bars = parse_bars(payload(days, "1d"), "1d", now)
        result = volume_from(bars, now)
        self.assertEqual((result["volume"], result["mean20"]), (20, 9.5))
        del bars[days[3]]
        self.assertIsNone(volume_from(bars, now)["mean20"])

    def test_rate_limit_rejection_and_preserved_quote(self):
        times = pd.date_range("2024-03-04T14:00Z", periods=2, freq="min")
        responses = {"1m": payload(times), "1d": b"{}"}
        calls = []
        def fetch(interval):
            calls.append(interval)
            return responses[interval]
        with tempfile.TemporaryDirectory() as tmp:
            market = LiveMarket(tmp, fetch)
            first = market.snapshot()
            market.snapshot()
            self.assertEqual(calls, ["1m", "1d"])
            market.next.clear()
            responses["1m"] = b'{"bad":true}'
            second = market.snapshot()
            self.assertTrue(second["quote"]["error"])
            self.assertEqual(first["quote"]["value"]["price"], 40.)
            self.assertEqual(first["quote"]["value"], second["quote"]["value"])
            raw, = (Path(tmp)/"quarantine"/"1m").glob("*/response.json.gz")
            self.assertEqual(gzip.decompress(raw.read_bytes()), responses["1m"])