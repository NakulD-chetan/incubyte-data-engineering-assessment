import json
import unittest
from datetime import date
from pathlib import Path

from skypoints.ingest import ingest_file
from skypoints.pipeline import connect


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        self.root = Path(__file__).resolve().parents[1]
        self.as_of = date(2024, 2, 3)
        self.updated = "2024-01-01T00:00:00+00:00"

    def test_flat_file_is_landed_quarantined_and_loaded(self):
        content = (self.root / "data/demo/member_feed.psv").read_bytes()
        result = ingest_file(self.db, "flat-1", "member_feed.psv", content, "flat", self.as_of, self.updated)
        self.assertEqual(result["accepted"], 2)
        self.assertEqual(result["rejected"][0]["line"], 4)
        self.assertEqual(self.db.execute("SELECT content, status FROM landed_file").fetchone(), (content, "loaded"))
        rejected = self.db.execute("SELECT line_number, raw_record, errors FROM rejected_record").fetchone()
        self.assertEqual(rejected[0], 4)
        self.assertIn("Invalid", rejected[1])
        self.assertIn("Enrollment_Date: invalid date", json.loads(rejected[2]))
        self.assertEqual(self.db.execute("SELECT row_number FROM staged_member ORDER BY row_number").fetchall(), [(2,), (3,)])
        self.assertFalse(ingest_file(self.db, "flat-1", "member_feed.psv", content, "flat", self.as_of, self.updated)["new_feed_loaded"])

    def test_bad_header_is_retained_as_failed(self):
        content = b"bad header\n"
        with self.assertRaisesRegex(ValueError, "header"):
            ingest_file(self.db, "bad", "bad.psv", content, "flat", self.as_of, self.updated)
        self.assertEqual(self.db.execute("SELECT content, status FROM landed_file").fetchone(), (content, "failed"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM current_member").fetchone()[0], 0)

    def test_csv_preserves_invalid_row_and_original_bytes(self):
        content = (self.root / "data/samples/australia.csv").read_bytes()
        result = ingest_file(self.db, "aus", "australia.csv", content, "australia", self.as_of, self.updated)
        self.assertEqual(result["accepted"], 2)
        self.assertEqual(self.db.execute("SELECT content FROM landed_file").fetchone()[0], content)
        self.assertEqual(self.db.execute("SELECT line_number FROM rejected_record").fetchone()[0], 3)
        self.assertEqual(self.db.execute("SELECT row_number FROM staged_member ORDER BY row_number").fetchall(), [(2,), (4,)])

    def test_feed_id_cannot_be_reused_for_different_bytes(self):
        content = (self.root / "data/demo/member_feed.psv").read_bytes()
        ingest_file(self.db, "f", "file.psv", content, "flat", self.as_of, self.updated)
        with self.assertRaisesRegex(ValueError, "differs"):
            ingest_file(self.db, "f", "file.psv", content + b"\n", "flat", self.as_of, self.updated)


if __name__ == "__main__":
    unittest.main()
