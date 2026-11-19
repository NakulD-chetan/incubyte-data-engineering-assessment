import json
import unittest

from skypoints.ingest_redemptions import ingest_redemption_file
from skypoints.pipeline import connect
from skypoints.redemptions import RedemptionError


class RedemptionFileTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        self.feed = {"member_id": "1", "feed_date": "20240115", "redemptions": [
            {"txn_id": "T1", "txn_date": "20240110", "partner": "Air", "miles_redeemed": 10, "status": "PENDING"}]}

    def test_valid_feed_is_saved_and_replayed(self):
        content = json.dumps(self.feed).encode()
        self.assertTrue(ingest_redemption_file(self.db, "r1", "feed.json", content))
        self.assertFalse(ingest_redemption_file(self.db, "r1", "feed.json", content))
        self.assertEqual(self.db.execute("SELECT content, status FROM landed_file").fetchone(), (content, "loaded"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM redemption_transaction").fetchone()[0], 1)

    def test_invalid_feed_remains_available_for_review(self):
        self.feed["redemptions"][0]["miles_redeemed"] = -1
        content = json.dumps(self.feed).encode()
        with self.assertRaises(RedemptionError):
            ingest_redemption_file(self.db, "bad", "feed.json", content)
        self.assertEqual(self.db.execute("SELECT content, status FROM landed_file").fetchone(), (content, "failed"))
        self.assertEqual(self.db.execute("SELECT count(*) FROM redemption_transaction").fetchone()[0], 0)

    def test_invalid_json_is_saved(self):
        with self.assertRaises(json.JSONDecodeError):
            ingest_redemption_file(self.db, "broken", "feed.json", b"{")
        self.assertEqual(self.db.execute("SELECT status FROM landed_file").fetchone()[0], "failed")


if __name__ == "__main__":
    unittest.main()
