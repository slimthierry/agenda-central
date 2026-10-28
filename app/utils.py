import secrets
from datetime import date as date_cls
from datetime import datetime, timezone


def now_iso() -> str:
    """ISO-8601 UTC au format identique à JS toISOString (millisecondes + Z)."""
    dt = datetime.now(timezone.utc)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


def weekday_of(date: str) -> int:
    """Jour de la semaine 0 (dimanche) … 6 (samedi) — équivalent JS getDay()."""
    y, m, d = (int(p) for p in date.split("-"))
    return (date_cls(y, m, d).weekday() + 1) % 7


def minutes_of(time: str) -> int:
    h, m = time.split(":")
    return int(h) * 60 + int(m)


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def overlaps(a_start: int, a_duration: int, b_start: int, b_duration: int) -> bool:
    return a_start < b_start + b_duration and b_start < a_start + a_duration


def random_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"
