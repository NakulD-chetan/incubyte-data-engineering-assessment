import unittest

from skypoints.current_members import MemberConflict, resolve_members


class CurrentMemberTests(unittest.TestCase):
    def setUp(self):
        self.old = {"member_id": "123", "country": "india", "member_name": "A",
                    "source_updated_at": "2024-01-01T00:00:00+00:00"}
        self.new = {**self.old, "country": "usa", "source_updated_at": "2024-02-01T00:00:00+00:00"}

    def test_latest_wins_even_when_records_arrive_out_of_order(self):
        result = resolve_members([self.new, self.old])
        self.assertEqual(result["india"], [])
        self.assertEqual(result["usa"], [self.new])

    def test_identical_replay_is_not_a_duplicate(self):
        result = resolve_members([self.old, self.old.copy()])
        self.assertEqual(result["india"], [self.old])

    def test_same_instant_with_different_timezone_is_replay(self):
        replay = {**self.old, "source_updated_at": "2024-01-01T05:30:00+05:30"}
        self.assertEqual(len(resolve_members([self.old, replay])["india"]), 1)

    def test_equal_time_with_conflicting_profiles_is_rejected(self):
        with self.assertRaisesRegex(MemberConflict, "conflicting"):
            resolve_members([self.old, {**self.old, "country": "usa"}])

    def test_missing_ordering_information_is_rejected(self):
        with self.assertRaisesRegex(MemberConflict, "source_updated_at"):
            resolve_members([{**self.old, "source_updated_at": None}])
        with self.assertRaisesRegex(MemberConflict, "source_updated_at"):
            resolve_members([{**self.old, "source_updated_at": "2024-01-01T00:00:00"}])

    def test_unknown_country_is_rejected(self):
        with self.assertRaisesRegex(MemberConflict, "unsupported country"):
            resolve_members([{**self.old, "country": "other"}])


if __name__ == "__main__":
    unittest.main()
