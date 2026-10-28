import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Appointment
from app.utils import now_iso

LEAD_DEFAULT_MIN = 60
POLL_INTERVAL_S = 45
ACTIVE_STATUSES = ["draft", "confirmed"]


def _start_datetime(a: Appointment) -> datetime:
    y, m, d = (int(p) for p in a.date.split("-"))
    hh, mm = a.time.split(":")
    return datetime(y, m, d, int(hh), int(mm), tzinfo=timezone.utc)


async def send_reminder(appt: Appointment) -> bool:
    """Envoie le rappel. Twilio si configure, sinon sender log (dev)."""
    lead_min = settings.reminder_lead_min or LEAD_DEFAULT_MIN
    if settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        body = (
            f"Cher patient, ce message vous rappelle votre rendez-vous : "
            f"{appt.date} a {appt.time} (duree {appt.duration_min} min)."
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"To": appt.patient_phone, "From": settings.twilio_from_number, "Body": body},
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
        return resp.status_code < 400
    print(f"[reminder:LOG] RDV {appt.date} {appt.time} patient={appt.patient_name} phone={appt.patient_phone} lead={lead_min}")
    return True


async def process_due(session: Session) -> list:
    """Renvoie les ids des rappels envoyes lors de ce tick."""
    now = datetime.now(timezone.utc)
    lead = timedelta(minutes=settings.reminder_lead_min or LEAD_DEFAULT_MIN)
    stmts = (
        select(Appointment)
        .where(
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.patient_phone.is_not(None),
            Appointment.patient_phone != "",
            Appointment.reminder_sent_at.is_(None),
        )
        .order_by(Appointment.date, Appointment.time)
    )
    due = []
    for appt in session.scalars(stmts).all():
        start = _start_datetime(appt)
        if start - lead <= now < start:
            due.append(appt)
    sent_ids = []
    for appt in due:
        if await send_reminder(appt):
            appt.reminder_sent_at = now_iso()
            sent_ids.append(appt.id)
    if sent_ids:
        session.commit()
    return sent_ids


async def _loop():
    from app.db import SessionLocal

    while True:
        with SessionLocal() as session:
            await process_due(session)
        await asyncio.sleep(POLL_INTERVAL_S)


_task = None


def start_reminder_loop():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


async def stop_reminder_loop():
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
