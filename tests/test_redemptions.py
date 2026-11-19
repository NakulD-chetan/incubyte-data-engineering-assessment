import unittest

from skypoints.redemptions import RedemptionError, flatten_feed, join_current_members


class RedemptionTests(unittest.TestCase):
    def setUp(self):
        self.transaction = {"txn_id": "RX1", "txn_date": "20240110", "partner": "AeroLink",
                            "miles_redeemed": 12000, "status": "COMPLETED"}
        self.feed = {"member_id": "223457", "feed_date": "20240115", "redemptions": [self.transaction]}

    def test_flattens_and_joins_or_preserves_unmatched(self):
        rows = flatten_feed(self.feed)
        self.assertEqual(rows[0]["transaction_date"], "2024-01-10")
        member = {"member_id": "223457", "country": "usa"}
        self.assertEqual(join_current_members(rows, {"usa": [member]})[0]["member"], member)
        self.assertIsNone(join_current_members(rows, {})[0]["member"])

    def test_bad_dates_and_miles_fail(self):
        for updates in ({"txn_date": "20241301"}, {"miles_redeemed": -1}, {"miles_redeemed": True}):
            with self.subTest(updates=updates), self.assertRaises(RedemptionError):
                flatten_feed({**self.feed, "redemptions": [{**self.transaction, **updates}]})

    def test_duplicate_transaction_handling(self):
        self.assertEqual(len(flatten_feed({**self.feed, "redemptions": [self.transaction, self.transaction]})), 1)
        with self.assertRaisesRegex(RedemptionError, "conflicting"):
            flatten_feed({**self.feed, "redemptions": [self.transaction, {**self.transaction, "miles_redeemed": 1}]})

    def test_empty_feed_and_pending_status(self):
        self.assertEqual(flatten_feed({**self.feed, "redemptions": []}), [])
        rows = flatten_feed({**self.feed, "redemptions": [{**self.transaction, "status": "PENDING"}]})
        self.assertEqual(rows[0]["status"], "PENDING")

    def test_duplicate_current_member_is_an_error(self):
        member = {"member_id": "223457"}
        with self.assertRaisesRegex(RedemptionError, "multiple current"):
            join_current_members(flatten_feed(self.feed), {"usa": [member], "india": [member]})


if __name__ == "__main__":
    unittest.main()
