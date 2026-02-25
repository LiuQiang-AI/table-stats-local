import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import storage


class SmokeTest(unittest.TestCase):
    def test_create_normalize_dates_and_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cfg = storage.default_config()
            cfg["defaultVehicle"] = "蒙J87721"
            cfg["defaultModel"] = "PAC"

            t = storage.create_table(cfg, "2026-02-25", 3)
            t = storage.normalize_table(cfg, t)
            self.assertEqual(t["startDate"], "2026-02-25")
            rows = t["rows"]
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["loadDate"], "2026-02-25")
            self.assertEqual(rows[1]["loadDate"], "2026-02-26")
            self.assertEqual(rows[2]["loadDate"], "2026-02-27")
            self.assertEqual(rows[0]["vehicle"], "蒙J87721")
            self.assertEqual(rows[0]["model"], "PAC")

            tables_dir = base / "tables"
            storage.save_table(tables_dir, t)
            t2 = storage.load_table_by_id(tables_dir, t["id"])
            self.assertIsInstance(t2, dict)
            self.assertEqual(t2["id"], t["id"])

    def test_amount_compute_and_summary_and_csv(self):
        cfg = storage.default_config()
        t = storage.create_table(cfg, "2026-02-25", 2)
        t["rows"][0]["freight"] = "100"
        t["rows"][0]["settleTons"] = "2.5"
        t = storage.normalize_table(cfg, t)
        self.assertEqual(t["rows"][0]["amount"], "250")

        t2, total = storage.summarize_table(cfg, t)
        self.assertEqual(total, Decimal("250"))
        self.assertEqual(t2["name"], "2026-02-25-2026-02-26")

        csv_bytes = storage.export_csv_bytes(t2)
        # UTF-8 BOM
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
        text = csv_bytes.decode("utf-8")
        self.assertIn("装车日期", text.splitlines()[0])


if __name__ == "__main__":
    unittest.main()

