"""Load normalized member events and redemption feeds into a local SQLite database."""

import argparse
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from skypoints.current_members import MemberConflict, resolve_members
from skypoints.redemptions import RedemptionError, flatten_feed


SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_feed (
    feed_id TEXT PRIMARY KEY, feed_type TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS landed_file (
    feed_id TEXT PRIMARY KEY, file_name TEXT NOT NULL, format TEXT NOT NULL,
    content BLOB NOT NULL, metadata TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rejected_record (
    feed_id TEXT NOT NULL, line_number INTEGER NOT NULL, raw_record TEXT NOT NULL,
    errors TEXT NOT NULL, PRIMARY KEY (feed_id, line_number),
    FOREIGN KEY (feed_id) REFERENCES landed_file(feed_id)
);
CREATE TABLE IF NOT EXISTS staged_member (
    feed_id TEXT NOT NULL, row_number INTEGER NOT NULL, member_id TEXT NOT NULL,
    member_name TEXT NOT NULL, country TEXT NOT NULL, enrollment_date TEXT NOT NULL,
    last_flight_date TEXT, date_of_birth TEXT, source_updated_at TEXT NOT NULL,
    processing_date TEXT NOT NULL, age INTEGER, stale_member INTEGER,
    PRIMARY KEY (feed_id, row_number)
);
CREATE TABLE IF NOT EXISTS member_event (
    member_id TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL,
    PRIMARY KEY (member_id, updated_at)
);
CREATE TABLE IF NOT EXISTS current_member (
    member_id TEXT PRIMARY KEY, country TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE VIEW IF NOT EXISTS table_india AS SELECT * FROM current_member WHERE country = 'india';
CREATE VIEW IF NOT EXISTS table_usa AS SELECT * FROM current_member WHERE country = 'usa';
CREATE VIEW IF NOT EXISTS table_australia AS SELECT * FROM current_member WHERE country = 'australia';
CREATE TABLE IF NOT EXISTS redemption_transaction (
    transaction_id TEXT PRIMARY KEY, member_id TEXT NOT NULL, transaction_date TEXT NOT NULL,
    partner TEXT NOT NULL, miles_redeemed INTEGER NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS redemption_observation (
    feed_id TEXT NOT NULL, transaction_id TEXT NOT NULL, feed_date TEXT NOT NULL,
    PRIMARY KEY (feed_id, transaction_id)
);
"""


def connect(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _claim_feed(db, feed_id, kind, payload):
    if not isinstance(feed_id, str) or not feed_id.strip():
        raise ValueError("feed_id is required")
    encoded = _encoded(payload)
    previous = db.execute("SELECT feed_type, payload FROM raw_feed WHERE feed_id = ?", (feed_id,)).fetchone()
    if previous:
        if previous != (kind, encoded):
            raise ValueError(f"{feed_id}: feed ID already used for different data")
        return False
    db.execute("INSERT INTO raw_feed VALUES (?, ?, ?)", (feed_id, kind, encoded))
    return True


def _parse_optional(value, name, processing_date, required=False):
    if value is None or value == "":
        if required:
            raise ValueError(f"{name}: required")
        return None
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name}: expected ISO date") from None
    if parsed > processing_date:
        raise ValueError(f"{name}: in the future")
    return parsed


def load_members(db, feed_id, records, processing_date, line_numbers=None):
    """Atomically stage and publish normalized member events; exact feeds replay safely."""
    if not isinstance(processing_date, date) or isinstance(processing_date, datetime):
        raise ValueError("processing_date must be a date")
    if not isinstance(records, list):
        raise ValueError("member feed must be an array")
    if line_numbers is None:
        line_numbers = list(range(1, len(records) + 1))
    if len(line_numbers) != len(records) or len(set(line_numbers)) != len(line_numbers):
        raise ValueError("line numbers must be unique and match records")
    with db:
        # Processing date is part of the feed identity because it affects derived values.
        if not _claim_feed(db, feed_id, "member", {"processing_date": processing_date.isoformat(), "records": records, "line_numbers": line_numbers}):
            return False
        for index, record in zip(line_numbers, records):
            if not isinstance(record, dict):
                raise ValueError("member record must be an object")
            member_id, name = record.get("member_id"), record.get("member_name")
            if not isinstance(member_id, str) or not member_id.strip() or len(member_id) > 18:
                raise ValueError("member_id: required, maximum 18 characters")
            if not isinstance(name, str) or not name.strip() or len(name) > 255:
                raise ValueError("member_name: required, maximum 255 characters")
            resolve_members([record])  # Validate identity, country, and ordering timestamp.
            enrolled = _parse_optional(record.get("enrollment_date"), "enrollment_date", processing_date, True)
            dob = _parse_optional(record.get("date_of_birth"), "date_of_birth", processing_date)
            flight = _parse_optional(record.get("last_flight_date"), "last_flight_date", processing_date)
            age = processing_date.year - dob.year - ((processing_date.month, processing_date.day) < (dob.month, dob.day)) if dob else None
            stale = int((processing_date - flight).days > 90) if flight else None
            updated = datetime.fromisoformat(record["source_updated_at"]).astimezone(timezone.utc).isoformat()
            # Derived values depend on the processing date, not the source event.
            content = {key: value for key, value in record.items() if key not in ("age", "stale_member")}
            content["source_updated_at"] = updated
            payload = _encoded(content)
            previous = db.execute("SELECT payload FROM member_event WHERE member_id = ? AND updated_at = ?", (member_id, updated)).fetchone()
            if previous and previous[0] != payload:
                raise MemberConflict(f"{member_id}: conflicting records share an update timestamp")
            db.execute("INSERT OR IGNORE INTO member_event VALUES (?, ?, ?)", (member_id, updated, payload))
            db.execute("INSERT INTO staged_member VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (feed_id, index, member_id, name, record["country"], enrolled.isoformat(),
                        flight.isoformat() if flight else None, dob.isoformat() if dob else None,
                        updated, processing_date.isoformat(), age, stale))
            current = db.execute("SELECT payload FROM member_event WHERE member_id = ? ORDER BY updated_at DESC LIMIT 1", (member_id,)).fetchone()
            profile = json.loads(current[0])
            db.execute("INSERT INTO current_member VALUES (?, ?, ?) ON CONFLICT(member_id) DO UPDATE SET country=excluded.country, payload=excluded.payload",
                       (member_id, profile["country"], current[0]))
    return True


def load_redemptions(db, feed_id, feed):
    """Atomically persist transactions, allowing exact replays across feeds."""
    rows = flatten_feed(feed)
    with db:
        if not _claim_feed(db, feed_id, "redemption", feed):
            return False
        for row in rows:
            values = tuple(row[key] for key in ("transaction_id", "member_id", "transaction_date", "partner", "miles_redeemed", "status"))
            # SQLite INTEGER is signed 64-bit, unlike Snowflake NUMBER(38,0).
            if row["miles_redeemed"] > 2**63 - 1:
                raise RedemptionError("miles_redeemed exceeds SQLite integer range")
            previous = db.execute("SELECT transaction_id, member_id, transaction_date, partner, miles_redeemed, status FROM redemption_transaction WHERE transaction_id = ?", (row["transaction_id"],)).fetchone()
            if previous and previous != values:
                raise RedemptionError(f"{row['transaction_id']}: conflicting transaction across feeds")
            db.execute("INSERT OR IGNORE INTO redemption_transaction VALUES (?, ?, ?, ?, ?, ?)", values)
            db.execute("INSERT INTO redemption_observation VALUES (?, ?, ?)", (feed_id, row["transaction_id"], row["feed_date"]))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "data" / "demo"
    profiles = json.loads((root / "pipeline_members.json").read_text(encoding="utf-8"))
    feeds = json.loads((root / "redemptions.json").read_text(encoding="utf-8"))
    with connect(args.database) as db:
        load_members(db, "demo-members", profiles, date(2024, 2, 3))
        for index, feed in enumerate(feeds, 1):
            load_redemptions(db, f"demo-redemptions-{index}", feed)
        print("Current members:", db.execute("SELECT member_id, country FROM current_member ORDER BY member_id").fetchall())
        print("Transactions and current country:", db.execute("SELECT t.transaction_id, t.member_id, m.country FROM redemption_transaction t LEFT JOIN current_member m ON m.member_id = t.member_id ORDER BY t.transaction_id").fetchall())


if __name__ == "__main__":
    main()
