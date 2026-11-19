"""Resolve current member profiles from ordered source records."""

from datetime import datetime, timezone


class MemberConflict(ValueError):
    """The source did not provide enough information to choose safely."""


def resolve_members(records):
    """Return the latest profile per member, grouped by country.

    Each valid profile needs a globally unique member_id, country, and an
    ISO-8601 source_updated_at timestamp with a UTC offset. Identical records
    at the same timestamp are safe to replay; conflicting ones are not.
    """
    latest = {}
    seen = {}
    for record in records:
        member_id = record.get("member_id")
        country = record.get("country")
        timestamp = record.get("source_updated_at")
        if not isinstance(member_id, str) or not member_id.strip():
            raise MemberConflict("member_id is required")
        if country not in ("india", "usa", "australia"):
            raise MemberConflict(f"{member_id}: unsupported country")
        try:
            updated_at = datetime.fromisoformat(timestamp)
            if updated_at.utcoffset() is None:
                raise ValueError("timezone required")
            updated_at = updated_at.astimezone(timezone.utc)
        except (ValueError, TypeError):
            raise MemberConflict(f"{member_id}: source_updated_at must include a timezone") from None
        content = {key: value for key, value in record.items() if key != "source_updated_at"}
        key = (member_id, updated_at)
        if key in seen and seen[key] != content:
            raise MemberConflict(f"{member_id}: conflicting records share an update timestamp")
        seen[key] = content
        existing = latest.get(member_id)
        if existing is None or updated_at > existing[0]:
            latest[member_id] = (updated_at, record.copy())
    countries = {country: [] for country in ("india", "usa", "australia")}
    for member_id in sorted(latest):
        profile = latest[member_id][1]
        countries[profile["country"]].append(profile)
    return countries
