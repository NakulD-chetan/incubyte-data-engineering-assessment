"""Validate and flatten partner redemption feeds."""

from datetime import datetime


class RedemptionError(ValueError):
    """A feed or transaction is invalid."""


def _required_text(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise RedemptionError(f"{field}: required text, maximum {limit} characters")
    return value.strip()


def _date(value, field):
    if not isinstance(value, str) or len(value) != 8 or not value.isascii() or not value.isdigit():
        raise RedemptionError(f"{field}: expected YYYYMMDD")
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        raise RedemptionError(f"{field}: invalid date") from None


def flatten_feed(feed):
    """Return validated transaction rows; reject an invalid feed as a whole."""
    if not isinstance(feed, dict):
        raise RedemptionError("feed: expected an object")
    member_id = _required_text(feed.get("member_id"), "member_id", 18)
    feed_date = _date(feed.get("feed_date"), "feed_date")
    transactions = feed.get("redemptions")
    if not isinstance(transactions, list):
        raise RedemptionError("redemptions: expected an array")
    rows = []
    seen = {}
    for index, transaction in enumerate(transactions):
        if not isinstance(transaction, dict):
            raise RedemptionError(f"redemptions[{index}]: expected an object")
        transaction_id = _required_text(transaction.get("txn_id"), "txn_id", 128)
        miles = transaction.get("miles_redeemed")
        if isinstance(miles, bool) or not isinstance(miles, int) or miles < 0 or miles >= 10**38:
            raise RedemptionError("miles_redeemed: expected a non-negative integer within 38 digits")
        row = {
            "transaction_id": transaction_id,
            "member_id": member_id,
            "feed_date": feed_date,
            "transaction_date": _date(transaction.get("txn_date"), "txn_date"),
            "partner": _required_text(transaction.get("partner"), "partner", 255),
            "miles_redeemed": miles,
            "status": _required_text(transaction.get("status"), "status", 32),
        }
        if transaction_id in seen:
            if seen[transaction_id] != row:
                raise RedemptionError(f"{transaction_id}: conflicting transactions")
            continue
        seen[transaction_id] = row
        rows.append(row)
    return rows


def join_current_members(transactions, country_tables):
    """Attach current profiles while retaining unmatched transactions."""
    members = {}
    for profiles in country_tables.values():
        for member in profiles:
            member_id = member["member_id"]
            if member_id in members:
                raise RedemptionError(f"{member_id}: multiple current profiles")
            members[member_id] = member
    return [{"transaction": row, "member": members.get(row["member_id"])} for row in transactions]
