"""Normalize and validate the supplied country member files."""

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path


FIELDS = {
    "india": {"member_id": "ID", "member_name": "Name", "date_of_birth": "DOB",
              "enrollment_date": "EnrollmentDate", "last_flight_date": "Flight Date", "tier_code": "TierCode"},
    "usa": {"member_id": "ID", "member_name": "Name", "enrollment_date": "EnrollmentDate",
            "last_flight_date": "FlightDate", "tier_code": "TierCode"},
    "australia": {"member_id": "Unique ID", "member_name": "Member Name", "date_of_birth": "Date of Birth",
                  "enrollment_date": "Date of Enrollment", "last_flight_date": "Date of Flight", "tier_code": "Tier Type"},
}
DATE_FIELDS = ("date_of_birth", "enrollment_date", "last_flight_date")


def parse_date(value, country):
    value = value.strip()
    if not value or value.upper() == "NULL":
        return None
    if country != "usa":
        return datetime.strptime(value, "%Y-%m-%d" if country == "australia" else "%m/%d/%Y").date()
    if not value.isascii() or not value.isdigit() or len(value) not in (7, 8):
        raise ValueError("expected compact month-day-year")
    year, prefix = int(value[-4:]), value[:-4]
    candidates = set()
    for month_digits in (1, 2):
        month, day = prefix[:month_digits], prefix[month_digits:]
        if not 1 <= len(day) <= 2:
            continue
        try:
            candidates.add(date(year, int(month), int(day)))
        except ValueError:
            pass
    if len(candidates) != 1:
        raise ValueError("invalid or ambiguous compact date")
    return candidates.pop()


def normalize(row, country, processing_date):
    mapping = FIELDS[country]
    member = {field: row.get(column, "").strip() for field, column in mapping.items()}
    member["country"] = country
    errors = []
    for field in ("member_id", "member_name", "enrollment_date"):
        if not member.get(field) or member[field].upper() == "NULL":
            errors.append(f"{field}: required")
    for field, limit in (("member_id", 18), ("member_name", 255), ("tier_code", 5)):
        if len(member.get(field, "")) > limit:
            errors.append(f"{field}: exceeds {limit} characters")
    for field in DATE_FIELDS:
        try:
            member[field] = parse_date(member.get(field, ""), country)
        except ValueError:
            errors.append(f"{field}: invalid or ambiguous date")
            member[field] = None
    dob, flight = member["date_of_birth"], member["last_flight_date"]
    if dob and dob > processing_date:
        errors.append("date_of_birth: in the future")
    if member["enrollment_date"] and member["enrollment_date"] > processing_date:
        errors.append("enrollment_date: in the future")
    if flight and flight > processing_date:
        errors.append("last_flight_date: in the future")
    member["age"] = (processing_date.year - dob.year - ((processing_date.month, processing_date.day) < (dob.month, dob.day))) if dob and dob <= processing_date else None
    member["stale_member"] = (processing_date - flight).days > 90 if flight and flight <= processing_date else None
    return member, errors


def read_members(path, country, processing_date):
    results = []
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = set(FIELDS[country].values()) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"line {line}: column count does not match header")
            member, errors = normalize(row, country, processing_date)
            results.append({"line": line, "member": member, "errors": errors})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("country", choices=FIELDS)
    parser.add_argument("file", type=Path)
    parser.add_argument("--processing-date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    try:
        results = read_members(args.file, args.country, args.processing_date)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(results, indent=2, default=str))
    return 1 if any(result["errors"] for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
