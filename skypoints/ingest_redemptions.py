"""Save and load a partner redemption JSON file."""

import argparse
import json
from pathlib import Path

from skypoints.pipeline import connect, load_redemptions


def ingest_redemption_file(db, feed_id, filename, content):
    if not isinstance(feed_id, str) or not feed_id.strip():
        raise ValueError("feed_id is required")
    with db:
        old = db.execute("SELECT file_name, format, content FROM landed_file WHERE feed_id = ?", (feed_id,)).fetchone()
        if old and old != (filename, "redemption", content):
            raise ValueError(f"{feed_id}: landed file differs")
        if not old:
            db.execute("INSERT INTO landed_file VALUES (?, ?, 'redemption', ?, '{}', 'landed')", (feed_id, filename, content))
    try:
        feed = json.loads(content.decode("utf-8-sig"))
        loaded = load_redemptions(db, feed_id, feed)
        with db:
            db.execute("UPDATE landed_file SET status='loaded' WHERE feed_id=?", (feed_id,))
        return loaded
    except Exception:
        with db:
            db.execute("UPDATE landed_file SET status='failed' WHERE feed_id=?", (feed_id,))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--feed-id", required=True)
    args = parser.parse_args()
    db = connect(args.database)
    try:
        loaded = ingest_redemption_file(db, args.feed_id, args.file.name, args.file.read_bytes())
    finally:
        db.close()
    print("Loaded new feed." if loaded else "Feed already loaded.")


if __name__ == "__main__":
    main()
