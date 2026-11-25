import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from data_manifest import write_data_manifest


class DataManifestTests(unittest.TestCase):
    def test_manifest_records_provenance_validation_and_file_hash(self):
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        prices = pd.Series([100.0, 110.0, 99.0], index=dates, name="PETR4")
        returns = 100.0 * (prices / prices.shift(1)).apply(math.log)
        returns = returns.dropna()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data" / "raw"
            data_dir.mkdir(parents=True)
            price_file = data_dir / "PETR4.csv"
            prices.to_frame("Close").to_csv(price_file)
            output = root / "runs" / "run_test" / "manifest.json"

            manifest = write_data_manifest(
                output,
                run_id="run_test",
                assets={"PETR4": "PETR4.SA"},
                prices={"PETR4": prices},
                returns={"PETR4": returns},
                data_directory=data_dir,
                sources={"PETR4": "cache_fallback_provider_unavailable"},
                settings={"alpha": 0.01},
            )

            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["run_id"], "run_test")
            self.assertEqual(manifest["assets"][0]["source_mode"], "cache_fallback_provider_unavailable")
            self.assertEqual(manifest["assets"][0]["sha256"], hashlib.sha256(price_file.read_bytes()).hexdigest())
            self.assertEqual(manifest["assets"][0]["return_count"], 2)
            self.assertEqual(manifest["assets"][0]["validation"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
