from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session, require_connector
from app.errors import AgendaError
from app.models import Appointment, Doctor, Establishment, doctor_establishments
from app.schemas import appointment_dict
from app.slots import free_slots, has_conflict
from app.utils import now_iso, random_id
from app.validate import (
    one_of,
    optional_string,
    read_body,
    require_date,
    require_int,
    require_string,
    require_time,
)

STATUSES = ["draft", "confirmed", "done", "canceled"]
EPOCH = "1970-01-01T00:00:00.000Z"

router = APIRouter(prefix="/connector", tags=["connecteur"])


def _linked_doctors(session: Session, establishment_id: str) -> list[Doctor]:
    stmt = (
        select(Doctor)
        .join(doctor_establishments, Doctor.id == doctor_establishments.c.doctor_id)
        .where(doctor_establishments.c.establishment_id == establishment_id)
        .order_by(Doctor.name)
    )
    return list(session.scalars(stmt))


@router.get("/slots")
def slots(
    request: Request,
    establishment: Establishment = Depends(require_connector),
    session: Session = Depends(get_session),
):
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

    doctors = _linked_doctors(session, establishment.id)
    doctor_filter = qp.get("doctor_id")
    if doctor_filter is not None:
        doctors = [d for d in doctors if d.id == doctor_filter]

    return {
        "establishment": {"id": establishment.id, "name": establishment.name},
        "date": date,
        "duration_min": duration,
        "doctors": [
            {
                "doctor_id": d.id,
                "doctor_name": d.name,
                "slots": free_slots(session, d.id, date, duration, establishment.id),
            }
            for d in doctors
        ],
    }


@router.post("/appointments", status_code=201)
async def push_appointment(
    request: Request,
    establishment: Establishment = Depends(require_connector),
    session: Session = Depends(get_session),
):
    body = await read_body(request)
    doctor_id = require_string(body, "doctor_id", max_len=64)
    linked = session.execute(
        select(doctor_establishments.c.doctor_id).where(
            doctor_establishments.c.doctor_id == doctor_id,
            doctor_establishments.c.establishment_id == establishment.id,
        )
    ).first()
    if linked is None:
        raise AgendaError(400, "Médecin non rattaché à cet établissement")

    now = now_iso()
    appt = Appointment(
        id=optional_string(body, "id", max_len=64) or random_id("cn"),
        doctor_id=doctor_id,
        establishment_id=establishment.id,
        patient_name=require_string(body, "patient_name", max_len=120),
        patient_phone=optional_string(body, "patient_phone", max_len=40),
        date=require_date(body, "date"),
        time=require_time(body, "time"),
        duration_min=require_int(body, "duration_min", min_val=5, max_val=240),
        reason=optional_string(body, "reason", max_len=300),
        status=one_of(body, "status", STATUSES, "confirmed"),
        source="connector",
        created_at=now,
        updated_at=now,
    )
    if has_conflict(session, appt.doctor_id, appt.date, appt.time, appt.duration_min):
        raise AgendaError(409, "Créneau déjà occupé pour ce médecin")
    session.add(appt)
    session.commit()
    return {"appointment": appointment_dict(appt)}


@router.get("/appointments")
def pull_appointments(
    request: Request,
    establishment: Establishment = Depends(require_connector),
    session: Session = Depends(get_session),
):
    since = request.query_params.get("since") or EPOCH
    stmt = (
        select(Appointment)
        .where(
            Appointment.establishment_id == establishment.id,
            Appointment.updated_at > since,
        )
        .order_by(Appointment.date, Appointment.time)
    )
    return {
        "appointments": [appointment_dict(a) for a in session.scalars(stmt)],
        "server_time": now_iso(),
    }


@router.patch("/appointments/{appointment_id}/status")
async def patch_status(
    appointment_id: str,
    request: Request,
    establishment: Establishment = Depends(require_connector),
    session: Session = Depends(get_session),
):
    appt = session.get(Appointment, appointment_id)
    if appt is None or appt.establishment_id != establishment.id:
        raise AgendaError(404, "Rendez-vous introuvable")
    body = await read_body(request)
    appt.status = one_of(body, "status", STATUSES)
    appt.updated_at = now_iso()
    session.commit()
    return {"appointment": appointment_dict(appt)}
