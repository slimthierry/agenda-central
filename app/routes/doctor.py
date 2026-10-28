from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_session, require_doctor
from app.errors import AgendaError
from app.models import Appointment, AvailabilityRule, Doctor, Establishment, doctor_establishments
from app.schemas import appointment_dict, doctor_public, establishment_dict, rule_dict
from app.slots import free_slots, has_conflict, list_availability
from app.utils import now_iso, random_id
from app.validate import (
    as_object,
    one_of,
    optional_string,
    read_body,
    require_date,
    require_int,
    require_string,
    require_time,
)

STATUSES = ["draft", "confirmed", "done", "canceled"]
SOURCES = ["app", "connector", "patient"]

router = APIRouter(prefix="/api", tags=["médecin"])


def _list_doctor_establishments(session: Session, doctor_id: str) -> list[Establishment]:
    stmt = (
        select(Establishment)
        .join(doctor_establishments, Establishment.id == doctor_establishments.c.establishment_id)
        .where(doctor_establishments.c.doctor_id == doctor_id)
        .order_by(Establishment.name)
    )
    return list(session.scalars(stmt))


def _require_own_appointment(session: Session, appointment_id: str, doctor_id: str) -> Appointment:
    appt = session.get(Appointment, appointment_id)
    if appt is None or appt.doctor_id != doctor_id:
        raise AgendaError(404, "Rendez-vous introuvable")
    return appt


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


# ---------- Profil ----------


@router.get("/me")
def me(doctor: Doctor = Depends(require_doctor), session: Session = Depends(get_session)):
    return {
        "doctor": doctor_public(doctor),
        "establishments": [establishment_dict(e) for e in _list_doctor_establishments(session, doctor.id)],
    }


# ---------- Établissements ----------


@router.get("/establishments")
def list_establishments(doctor: Doctor = Depends(require_doctor), session: Session = Depends(get_session)):
    return {"establishments": [establishment_dict(e) for e in _list_doctor_establishments(session, doctor.id)]}


@router.post("/establishments", status_code=201)
async def create_establishment(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    body = await read_body(request)
    name = require_string(body, "name", max_len=120)
    est_id = optional_string(body, "id", max_len=64) or random_id("est")
    est = Establishment(
        id=est_id,
        name=name,
        address=optional_string(body, "address", max_len=200),
        color=optional_string(body, "color", max_len=20) or "#179F4E",
        connector_key=f"conn-{est_id}",
        created_at=now_iso(),
    )
    session.add(est)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise AgendaError(409, "Établissement déjà existant") from None
    link = session.execute(
        select(doctor_establishments.c.doctor_id).where(
            doctor_establishments.c.doctor_id == doctor.id,
            doctor_establishments.c.establishment_id == est_id,
        )
    ).first()
    if link is None:
        session.execute(
            doctor_establishments.insert().values(doctor_id=doctor.id, establishment_id=est_id)
        )
    session.commit()
    return {"establishment": establishment_dict(est)}


@router.delete("/establishments/{establishment_id}", status_code=204)
def delete_establishment(
    establishment_id: str,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    est = session.get(Establishment, establishment_id)
    if est is None:
        raise AgendaError(404, "Établissement introuvable")
    session.execute(
        sa_delete(doctor_establishments).where(
            doctor_establishments.c.doctor_id == doctor.id,
            doctor_establishments.c.establishment_id == establishment_id,
        )
    )
    session.commit()
    return Response(status_code=204)


# ---------- Disponibilités ----------


@router.get("/availability")
def get_availability(doctor: Doctor = Depends(require_doctor), session: Session = Depends(get_session)):
    return {"rules": [rule_dict(r) for r in list_availability(session, doctor.id)]}


@router.put("/availability")
async def put_availability(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    body = await read_body(request)
    raw = body.get("rules")
    if not isinstance(raw, list):
        raise AgendaError(400, "rules[] attendu")
    rules = []
    for item in raw:
        o = as_object(item)
        rules.append(
            {
                "establishment_id": optional_string(o, "establishment_id", max_len=64),
                "weekday": require_int(o, "weekday", min_val=0, max_val=6),
                "start": require_time(o, "start"),
                "end": require_time(o, "end"),
            }
        )
    for r in rules:
        if r["start"] >= r["end"]:
            raise AgendaError(400, "start doit précéder end")
    session.execute(sa_delete(AvailabilityRule).where(AvailabilityRule.doctor_id == doctor.id))
    for r in rules:
        session.add(
            AvailabilityRule(
                id=random_id("av"),
                doctor_id=doctor.id,
                establishment_id=r["establishment_id"],
                weekday=r["weekday"],
                start_at=r["start"],
                end_at=r["end"],
            )
        )
    session.commit()
    return {"rules": [rule_dict(r) for r in list_availability(session, doctor.id)]}


# ---------- Créneaux ----------


@router.get("/slots")
def slots(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    date, duration, establishment_id = _parse_slots_query(request)
    slots = free_slots(session, doctor.id, date, duration, establishment_id)
    return {"date": date, "duration_min": duration, "slots": slots}


# ---------- Rendez-vous ----------


@router.get("/appointments")
def list_appointments(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    qp = request.query_params
    conditions = [Appointment.doctor_id == doctor.id]
    for field in ("date", "establishment_id", "status"):
        value = qp.get(field)
        if value is not None:
            conditions.append(getattr(Appointment, field) == value)
    appts = session.scalars(
        select(Appointment).where(*conditions).order_by(Appointment.date, Appointment.time)
    )
    return {"appointments": [appointment_dict(a) for a in appts]}


@router.get("/appointments/{appointment_id}")
def get_appointment(
    appointment_id: str,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    return {"appointment": appointment_dict(_require_own_appointment(session, appointment_id, doctor.id))}


@router.post("/appointments", status_code=201)
async def create_appointment(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    body = await read_body(request)
    now = now_iso()
    appt = Appointment(
        id=optional_string(body, "id", max_len=64) or random_id("ap"),
        doctor_id=doctor.id,
        establishment_id=require_string(body, "establishment_id", max_len=64),
        patient_name=require_string(body, "patient_name", max_len=120),
        patient_phone=optional_string(body, "patient_phone", max_len=40),
        date=require_date(body, "date"),
        time=require_time(body, "time"),
        duration_min=require_int(body, "duration_min", min_val=5, max_val=240),
        reason=optional_string(body, "reason", max_len=300),
        status=one_of(body, "status", STATUSES, "draft"),
        source=one_of(body, "source", SOURCES, "app"),
        created_at=now,
        updated_at=now,
        series_id=optional_string(body, "series_id", max_len=64),
        reminder_sent_at=optional_string(body, "reminder_sent_at", max_len=40),
    )
    if has_conflict(session, appt.doctor_id, appt.date, appt.time, appt.duration_min):
        raise AgendaError(409, "Créneau déjà occupé pour ce médecin")
    session.add(appt)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AgendaError(409, "Rendez-vous déjà existant") from None
    return {"appointment": appointment_dict(appt)}


@router.patch("/appointments/{appointment_id}")
async def patch_appointment(
    appointment_id: str,
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    existing = _require_own_appointment(session, appointment_id, doctor.id)
    body = await read_body(request)
    patch: dict = {}
    if "patient_name" in body:
        patch["patient_name"] = require_string(body, "patient_name", max_len=120)
    if "patient_phone" in body:
        patch["patient_phone"] = optional_string(body, "patient_phone", max_len=40)
    if "date" in body:
        patch["date"] = require_date(body, "date")
    if "time" in body:
        patch["time"] = require_time(body, "time")
    if "duration_min" in body:
        patch["duration_min"] = require_int(body, "duration_min", min_val=5, max_val=240)
    if "reason" in body:
        patch["reason"] = optional_string(body, "reason", max_len=300)
    if "status" in body:
        patch["status"] = one_of(body, "status", STATUSES)
    if "establishment_id" in body:
        patch["establishment_id"] = require_string(body, "establishment_id", max_len=64)

    touches_slot = any(f in patch for f in ("date", "time", "duration_min"))
    if touches_slot:
        status = patch.get("status", existing.status)
        if status != "canceled" and has_conflict(
            session,
            existing.doctor_id,
            patch.get("date", existing.date),
            patch.get("time", existing.time),
            patch.get("duration_min", existing.duration_min),
            exclude_id=existing.id,
        ):
            raise AgendaError(409, "Créneau déjà occupé pour ce médecin")

    if touches_slot:
        existing.reminder_sent_at = None
    if "series_id" in body:
        existing.series_id = optional_string(body, "series_id", max_len=64)

    for key, value in patch.items():
        setattr(existing, key, value)
    existing.updated_at = now_iso()
    session.commit()
    return {"appointment": appointment_dict(existing)}


@router.delete("/appointments/{appointment_id}", status_code=204)
def delete_appointment(
    appointment_id: str,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    existing = _require_own_appointment(session, appointment_id, doctor.id)
    session.delete(existing)
    session.commit()
    return Response(status_code=204)
