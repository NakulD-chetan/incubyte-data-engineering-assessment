"""Load valid sample CSV rows using explicitly supplied source metadata."""

import argparse
import json
from datetime import date
from pathlib import Path

from skypoints.members import FIELDS, read_members
from skypoints.pipeline import connect, load_members


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("country", choices=FIELDS)
    parser.add_argument("file", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--feed-id", required=True)
    parser.add_argument("--processing-date", required=True, type=date.fromisoformat)
    parser.add_argument("--source-updated-at", required=True, help="ISO-8601 timestamp with timezone, supplied by the source")
    parser.add_argument("--assume-global-ids", required=True, action="store_true", help="confirm source IDs are globally unique")
    args = parser.parse_args()
    rows = read_members(args.file, args.country, args.processing_date)
    rejected = [{"line": row["line"], "errors": row["errors"]} for row in rows if row["errors"]]
    accepted = []
    for row in rows:
        if not row["errors"]:
            member = {key: value.isoformat() if isinstance(value, date) else value for key, value in row["member"].items()}
            member["source_updated_at"] = args.source_updated_at
            accepted.append(member)
    db = connect(args.database)
    try:
        loaded = load_members(db, args.feed_id, accepted, args.processing_date)
    finally:
        db.close()
    print(json.dumps({"accepted": len(accepted), "rejected": rejected, "new_feed_loaded": loaded}, indent=2))


if __name__ == "__main__":
    main()
