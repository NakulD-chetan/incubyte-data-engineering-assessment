import unittest
from datetime import date
from pathlib import Path

from skypoints.members import read_members
from skypoints.pipeline import connect, load_members, load_redemptions
from skypoints.redemptions import RedemptionError


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        self.processing_date = date(2024, 2, 3)
        self.member = {"member_id": "1", "member_name": "Sam", "country": "india", "enrollment_date": "2020-01-01",
                       "last_flight_date": "2024-01-01", "date_of_birth": "2000-01-01", "source_updated_at": "2024-01-01T00:00:00+00:00"}
        self.feed = {"member_id": "1", "feed_date": "20240203", "redemptions": [{"txn_id": "T1", "txn_date": "20240201", "partner": "A", "miles_redeemed": 10, "status": "PENDING"}]}

    def test_move_replay_and_staging(self):
        self.assertTrue(load_members(self.db, "f1", [self.member], self.processing_date))
        self.assertFalse(load_members(self.db, "f1", [self.member], self.processing_date))
        moved = {**self.member, "country": "usa", "source_updated_at": "2024-02-01T00:00:00+00:00"}
        load_members(self.db, "f2", [moved], self.processing_date)
        self.assertEqual(self.db.execute("SELECT count(*) FROM table_india").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT member_id FROM table_usa").fetchone()[0], "1")
        self.assertEqual(self.db.execute("SELECT age, stale_member FROM staged_member WHERE feed_id='f1'").fetchone(), (24, 0))
        load_members(self.db, "late", [self.member], self.processing_date)
        self.assertEqual(self.db.execute("SELECT country FROM current_member").fetchone()[0], "usa")

    def test_bad_member_rolls_back_entire_feed(self):
        with self.assertRaises(ValueError):
            load_members(self.db, "bad", [self.member, {**self.member, "member_id": ""}], self.processing_date)
        self.assertEqual(self.db.execute("SELECT count(*) FROM raw_feed").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM current_member").fetchone()[0], 0)

    def test_transaction_replay_conflict_and_unmatched_join(self):
        load_redemptions(self.db, "r1", self.feed)
        load_redemptions(self.db, "r2", {**self.feed, "feed_date": "20240204"})
        self.assertEqual(self.db.execute("SELECT count(*) FROM redemption_transaction").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM redemption_observation").fetchone()[0], 2)
        conflict = {**self.feed, "redemptions": [{**self.feed["redemptions"][0], "miles_redeemed": 20}]}
        with self.assertRaises(RedemptionError):
            load_redemptions(self.db, "r3", conflict)
        self.assertIsNone(self.db.execute("SELECT feed_id FROM raw_feed WHERE feed_id='r3'").fetchone())
        self.assertIsNone(self.db.execute("SELECT m.country FROM redemption_transaction t LEFT JOIN current_member m ON t.member_id=m.member_id").fetchone()[0])

    def test_normalized_sample_can_be_loaded_with_source_metadata(self):
        path = Path(__file__).resolve().parents[1] / "data/samples/india.csv"
        rows = read_members(path, "india", self.processing_date)
        row = rows[0]
        self.assertFalse(row["errors"])
        member = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in row["member"].items()}
        member["source_updated_at"] = "2024-01-01T00:00:00+00:00"
        load_members(self.db, "sample-with-assumed-order", [member], self.processing_date)
        self.assertEqual(self.db.execute("SELECT member_name FROM staged_member").fetchone()[0], "Vikas")


if __name__ == "__main__":
    unittest.main()
