from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.errors import AgendaError
from app.models import Appointment, Doctor, Establishment, doctor_establishments
from app.schemas import appointment_dict, doctor_public, establishment_dict
from app.slots import free_slots, has_conflict
from app.utils import now_iso, random_id
from app.validate import (
    optional_string,
    read_body,
    require_date,
    require_int,
    require_string,
    require_time,
)

router = APIRouter(prefix="/booking", tags=["patient"])


def _require_doctor(session: Session, slug: str) -> Doctor:
    doctor = session.scalar(select(Doctor).where(Doctor.slug == slug))
    if doctor is None:
        raise AgendaError(404, "Médecin introuvable")
    return doctor


def _list_establishments(session: Session, doctor_id: str) -> list[Establishment]:
    stmt = (
        select(Establishment)
        .join(doctor_establishments, Establishment.id == doctor_establishments.c.establishment_id)
        .where(doctor_establishments.c.doctor_id == doctor_id)
        .order_by(Establishment.name)
    )
    return list(session.scalars(stmt))


def _parse_slots_query(request: Request) -> tuple[str, int, str | None]:
    qp = request.query_params
    date = require_date({"date": qp.get("date")}, "date")
    raw = qp.get("duration")
    if raw is None:
        duration = 30
    else:
        try:
            f = float(raw)
        except ValueError:
            raise AgendaError(400, "duration invalide") from None
        if not f.is_integer() or f < 5 or f > 240:
            raise AgendaError(400, "duration invalide")
        duration = int(f)
    return date, duration, qp.get("establishment_id") or None


@router.get("/{slug}")
def booking_info(slug: str, session: Session = Depends(get_session)):
    doctor = _require_doctor(session, slug)
    return {
        "doctor": doctor_public(doctor),
        "establishments": [establishment_dict(e) for e in _list_establishments(session, doctor.id)],
    }


@router.get("/{slug}/slots")
def slots(
    slug: str,
    request: Request,
    session: Session = Depends(get_session),
):
    doctor = _require_doctor(session, slug)
    date, duration, establishment_id = _parse_slots_query(request)
    slots = free_slots(session, doctor.id, date, duration, establishment_id)
    return {
        "doctor": {"id": doctor.id, "name": doctor.name, "slug": doctor.slug},
        "date": date,
        "duration_min": duration,
        "slots": slots,
    }


@router.post("/{slug}/appointments", status_code=201)
async def book(
    slug: str,
    request: Request,
    session: Session = Depends(get_session),
):
    doctor = _require_doctor(session, slug)
    body = await read_body(request)
    appt = Appointment(
        id=optional_string(body, "id", max_len=64) or random_id("bk"),
        doctor_id=doctor.id,
        establishment_id=require_string(body, "establishment_id", max_len=64),
        patient_name=require_string(body, "patient_name", max_len=120),
        patient_phone=optional_string(body, "patient_phone", max_len=40),
        date=require_date(body, "date"),
        time=require_time(body, "time"),
        duration_min=require_int(body, "duration_min", min_val=5, max_val=240),
        reason=optional_string(body, "reason", max_len=300),
        status="confirmed",
        source="patient",
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    if has_conflict(session, appt.doctor_id, appt.date, appt.time, appt.duration_min):
        raise AgendaError(409, "Ce créneau vient d’être pris, choisissez-en un autre.")
    session.add(appt)
    session.commit()
    return {"appointment": appointment_dict(appt)}


@router.get("/appointments/{appointment_id}")
def track(appointment_id: str, session: Session = Depends(get_session)):
    appt = session.get(Appointment, appointment_id)
    if appt is None:
        raise AgendaError(404, "Rendez-vous introuvable")
    return {"appointment": appointment_dict(appt)}
