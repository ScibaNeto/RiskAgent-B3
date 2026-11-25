import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from known_prices import get_observations


class KnownPricesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        for day, value in [("02", 100), ("04", 110)]:
            root = self.base / "phase1" / "runs" / day
            root.mkdir(parents=True)
            csv = root / "A.csv"
            csv.write_text(f"Date,Close\n2026-01-02,{value}\n", encoding="utf8")
            entry = dict(asset="A", provider="fixture", validation={"status": "passed"},
                         quality={"snapshot": "A.csv", "excluded_dates": []},
                         sha256=hashlib.sha256(csv.read_bytes()).hexdigest(), price_count=1,
                         start_date="2026-01-02", end_date="2026-01-02")
            (root / "manifest.json").write_text(json.dumps(dict(schema_version=2, assets=[entry],
                created_at_utc=f"2026-02-{day}T12:00:00Z")), encoding="utf8")

    def test_revision_only_after_availability(self):
        for t, price in [("2026-02-03T12:00Z", 100), ("2026-02-04T09:00-03:00", 110)]:
            values, _ = get_observations("A", t, self.base)
            self.assertEqual(values.iloc[0], price)

    def test_before_first_snapshot(self):
        with self.assertRaises(LookupError):
            get_observations("A", "2026-02-02T11:59Z", self.base)

    def test_tampering_is_detected(self):
        (self.base / "phase1/runs/04/A.csv").write_bytes(b"alterado")
        with self.assertRaisesRegex(ValueError, "Hash"):
            get_observations("A", "2026-02-05T12:00Z", self.base)
