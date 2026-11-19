"""Run a local demonstration using sample files and synthetic events."""

import json
from datetime import date
from pathlib import Path

from skypoints.current_members import resolve_members
from skypoints.members import read_members
from skypoints.redemptions import flatten_feed, join_current_members


ROOT = Path(__file__).resolve().parents[1]


def run_demo(root=ROOT):
    sample_results = {}
    for country in ("india", "usa", "australia"):
        rows = read_members(root / "data" / "samples" / f"{country}.csv", country, date(2023, 1, 1))
        sample_results[country] = {
            "accepted": sum(not row["errors"] for row in rows),
            "rejected": [{"line": row["line"], "errors": row["errors"]} for row in rows if row["errors"]],
        }
    demo_dir = root / "data" / "demo"
    profiles = json.loads((demo_dir / "member_updates.json").read_text(encoding="utf-8"))
    feeds = json.loads((demo_dir / "redemptions.json").read_text(encoding="utf-8"))
    countries = resolve_members(profiles)
    transactions = [transaction for feed in feeds for transaction in flatten_feed(feed)]
    return {
        "sample_validation_as_of": "2023-01-01",
        "sample_validation": sample_results,
        "synthetic_current_members": countries,
        "synthetic_redemptions": join_current_members(transactions, countries),
    }


def main():
    print(json.dumps(run_demo(), indent=2))


if __name__ == "__main__":
    main()
