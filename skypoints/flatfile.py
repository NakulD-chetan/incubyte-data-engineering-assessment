"""Read the assessment's pipe-delimited member feed."""

import csv
import io
from datetime import datetime


HEADER = ["Member_Name", "Member_Id", "Enrollment_Date", "Last_Flight_Date", "Tier_Code",
          "Agent_Name", "State", "Country", "DOB", "Is_Active"]
COUNTRIES = {"IND": "india", "USA": "usa", "AU": "australia", "AUS": "australia"}


def read_flatfile(text, processing_date):
    """Validate the specified H/D layout; return valid profiles and rejected lines."""
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="|", strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("empty flat file") from None
    if header != ["", "H", *HEADER]:
        raise ValueError("invalid flat-file header")
    accepted, rejected = [], []
    for fields in reader:
        line = reader.line_num
        errors = []
        if len(fields) != len(HEADER) + 2 or fields[:2] != ["", "D"]:
            rejected.append({"line": line, "raw_record": "|".join(fields), "errors": ["invalid detail layout"]})
            continue
        data = dict(zip(HEADER, (value.strip() for value in fields[2:])))
        for key, limit, required in (("Member_Name", 255, True), ("Member_Id", 18, True),
                                     ("Tier_Code", 5, False), ("Agent_Name", 255, False),
                                     ("State", 5, False), ("Country", 5, True), ("Is_Active", 1, False)):
            if required and not data[key]:
                errors.append(f"{key}: required")
            if len(data[key]) > limit:
                errors.append(f"{key}: exceeds {limit} characters")
        country = COUNTRIES.get(data["Country"].upper())
        if data["Country"] and not country:
            errors.append("Country: unsupported country")
        dates = {}
        for key, fmt, required in (("Enrollment_Date", "%Y%m%d", True), ("Last_Flight_Date", "%Y%m%d", False), ("DOB", "%m%d%Y", False)):
            value = data[key]
            dates[key] = None
            if not value or value.upper() == "NULL":
                if required:
                    errors.append(f"{key}: required")
                continue
            try:
                if len(value) != 8 or not value.isascii() or not value.isdigit():
                    raise ValueError
                parsed = datetime.strptime(value, fmt).date()
                if parsed > processing_date:
                    errors.append(f"{key}: in the future")
                else:
                    dates[key] = parsed.isoformat()
            except ValueError:
                errors.append(f"{key}: invalid date")
        if errors:
            rejected.append({"line": line, "raw_record": "|".join(fields), "errors": errors})
        else:
            accepted.append({"line": line, "member": {
                "member_name": data["Member_Name"], "member_id": data["Member_Id"],
                "enrollment_date": dates["Enrollment_Date"], "last_flight_date": dates["Last_Flight_Date"],
                "date_of_birth": dates["DOB"], "tier_code": data["Tier_Code"], "agent_name": data["Agent_Name"],
                "state": data["State"], "country": country, "active_member": data["Is_Active"]}})
    return accepted, rejected
