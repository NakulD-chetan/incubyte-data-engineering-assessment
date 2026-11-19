"""Land and load country CSV or pipe-delimited member files."""

import argparse
import io
import json
from datetime import date
from pathlib import Path

from skypoints.flatfile import read_flatfile
from skypoints.members import FIELDS, read_member_stream
from skypoints.pipeline import connect, load_members


def ingest_file(db, feed_id, filename, content, file_format, processing_date, source_updated_at):
    """Persist exact input bytes first, then validate, quarantine, and publish rows."""
    metadata = json.dumps({"processing_date": processing_date.isoformat(), "source_updated_at": source_updated_at}, sort_keys=True)
    with db:
        old = db.execute("SELECT file_name, format, content, metadata FROM landed_file WHERE feed_id = ?", (feed_id,)).fetchone()
        if old and old != (filename, file_format, content, metadata):
            raise ValueError(f"{feed_id}: landed file or metadata differs")
        if not old:
            db.execute("INSERT INTO landed_file VALUES (?, ?, ?, ?, ?, 'landed')", (feed_id, filename, file_format, content, metadata))
    try:
        text = content.decode("utf-8-sig")
        if file_format == "flat":
            accepted, rejected = read_flatfile(text, processing_date)
        elif file_format in FIELDS:
            results = read_member_stream(io.StringIO(text, newline=""), file_format, processing_date)
            accepted = [{"line": row["line"], "member": row["member"]} for row in results if not row["errors"]]
            lines = text.splitlines()
            rejected = [{"line": row["line"], "raw_record": "\n".join(lines[row["line"] - 1:row["end_line"]]), "errors": row["errors"]} for row in results if row["errors"]]
        else:
            raise ValueError("unknown file format")
        with db:
            for row in rejected:
                db.execute("INSERT OR REPLACE INTO rejected_record VALUES (?, ?, ?, ?)",
                           (feed_id, row["line"], row["raw_record"], json.dumps(row["errors"])))
        profiles = []
        for row in accepted:
            member = {key: value.isoformat() if isinstance(value, date) else value for key, value in row["member"].items()}
            member["source_updated_at"] = source_updated_at
            profiles.append(member)
        loaded = load_members(db, feed_id, profiles, processing_date, [row["line"] for row in accepted])
        with db:
            db.execute("UPDATE landed_file SET status='loaded' WHERE feed_id=?", (feed_id,))
        return {"accepted": len(accepted), "rejected": rejected, "new_feed_loaded": loaded}
    except Exception:
        with db:
            db.execute("UPDATE landed_file SET status='failed' WHERE feed_id=?", (feed_id,))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format", choices=[*FIELDS, "flat"])
    parser.add_argument("file", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--feed-id", required=True)
    parser.add_argument("--processing-date", required=True, type=date.fromisoformat)
    parser.add_argument("--source-updated-at", required=True, help="ISO-8601 timestamp with timezone, supplied by the source")
    parser.add_argument("--assume-global-ids", required=True, action="store_true", help="confirm source IDs are globally unique")
    args = parser.parse_args()
    db = connect(args.database)
    try:
        result = ingest_file(db, args.feed_id, args.file.name, args.file.read_bytes(), args.format, args.processing_date, args.source_updated_at)
    finally:
        db.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
