import unittest
from datetime import date
from pathlib import Path

from skypoints.members import normalize, parse_date, read_members


class MemberTests(unittest.TestCase):
    def test_compact_dates_reject_ambiguity(self):
        self.assertEqual(parse_date("6152022", "usa"), date(2022, 6, 15))
        with self.assertRaises(ValueError):
            parse_date("1052022", "usa")

    def test_stale_boundary_and_age(self):
        row = {"ID": "1", "Name": "A", "DOB": "1/2/2000", "EnrollmentDate": "1/1/2020",
               "Flight Date": "10/3/2022", "TierCode": "GLD"}
        member, errors = normalize(row, "india", date(2023, 1, 1))
        self.assertFalse(errors)
        self.assertEqual(member["age"], 22)
        self.assertFalse(member["stale_member"])
        member, _ = normalize(row, "india", date(2023, 1, 2))
        self.assertEqual(member["age"], 23)
        self.assertTrue(member["stale_member"])

    def test_missing_optional_dates_are_unknown(self):
        row = {"ID": "1", "Name": "A", "EnrollmentDate": "6152022", "FlightDate": "", "TierCode": "PLT"}
        member, errors = normalize(row, "usa", date(2023, 1, 1))
        self.assertFalse(errors)
        self.assertIsNone(member["age"])
        self.assertIsNone(member["stale_member"])

    def test_australian_sample_reports_invalid_enrollment(self):
        path = Path(__file__).resolve().parents[1] / "data/samples/australia.csv"
        results = read_members(path, "australia", date(2023, 1, 1))
        self.assertIn("enrollment_date: invalid or ambiguous date", results[1]["errors"])
        self.assertFalse(results[0]["errors"])

    def test_missing_columns_fail_file(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "members.csv"
            path.write_text("ID,Name\n1,A\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                read_members(path, "usa", date(2023, 1, 1))


if __name__ == "__main__":
    unittest.main()
