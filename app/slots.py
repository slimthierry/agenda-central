from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, AvailabilityRule
from app.utils import hhmm, minutes_of, overlaps, weekday_of


def list_availability(session: Session, doctor_id: str) -> list[AvailabilityRule]:
    stmt = (
        select(AvailabilityRule)
        .where(AvailabilityRule.doctor_id == doctor_id)
        .order_by(AvailabilityRule.weekday, AvailabilityRule.start_at)
    )
    return list(session.scalars(stmt))


def _day_appointments(session: Session, doctor_id: str, date: str) -> list[Appointment]:
    stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.date == date,
        Appointment.status != "canceled",
    )
    return list(session.scalars(stmt))


def has_conflict(
    session: Session,
    doctor_id: str,
    date: str,
    time: str,
    duration_min: int,
    exclude_id: str | None = None,
) -> bool:
    start = minutes_of(time)
    return any(
        a.id != exclude_id
        and overlaps(start, duration_min, minutes_of(a.time), a.duration_min)
        for a in _day_appointments(session, doctor_id, date)
    )


def free_slots(
    session: Session,
    doctor_id: str,
    date: str,
    duration_min: int,
    establishment_id: str | None = None,
) -> list[str]:
    weekday = weekday_of(date)
    rules = [
        r
        for r in list_availability(session, doctor_id)
        if r.weekday == weekday
        and (not r.establishment_id or not establishment_id or r.establishment_id == establishment_id)
    ]
    taken = _day_appointments(session, doctor_id, date)
    slots: set[str] = set()
    for rule in rules:
        frm = minutes_of(rule.start_at)
        to = minutes_of(rule.end_at)
        t = frm
        while t + duration_min <= to:
            time = hhmm(t)
            busy = any(
                overlaps(t, duration_min, minutes_of(a.time), a.duration_min) for a in taken
            )
            if not busy:
                slots.add(time)
            t += duration_min
    return sorted(slots)
