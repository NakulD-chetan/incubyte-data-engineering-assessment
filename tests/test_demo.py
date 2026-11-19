import unittest

from skypoints.demo import run_demo


class DemoTests(unittest.TestCase):
    def test_demo_shows_validation_move_and_unmatched_transaction(self):
        result = run_demo()
        self.assertEqual(result["sample_validation"]["australia"]["rejected"][0]["line"], 3)
        self.assertEqual(result["synthetic_current_members"]["india"], [])
        self.assertEqual(result["synthetic_current_members"]["usa"][0]["member_id"], "DEMO-1")
        self.assertEqual(result["synthetic_redemptions"][0]["member"]["country"], "usa")
        self.assertIsNone(result["synthetic_redemptions"][1]["member"])


if __name__ == "__main__":
    unittest.main()
