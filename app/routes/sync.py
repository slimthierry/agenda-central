from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session, require_doctor
from app.errors import AgendaError
from app.models import Appointment, Doctor
from app.schemas import appointment_dict
from app.utils import now_iso
from app.validate import (
    as_object,
    one_of,
    optional_iso,
    optional_string,
    read_body,
    require_date,
    require_int,
    require_string,
    require_time,
)

STATUSES = ["draft", "confirmed", "done", "canceled"]
SOURCES = ["app", "connector", "patient"]
EPOCH = "1970-01-01T00:00:00.000Z"

router = APIRouter(prefix="/api/sync", tags=["synchro"])


@router.get("/appointments")
def pull(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    since = request.query_params.get("since") or EPOCH
    stmt = (
        select(Appointment)
        .where(Appointment.doctor_id == doctor.id, Appointment.updated_at > since)
        .order_by(Appointment.date, Appointment.time)
    )
    return {
        "appointments": [appointment_dict(a) for a in session.scalars(stmt)],
        "server_time": now_iso(),
    }


@router.post("/appointments")
async def push(
    request: Request,
    doctor: Doctor = Depends(require_doctor),
    session: Session = Depends(get_session),
):
    body = await read_body(request)
    raw = body.get("appointments")
    if not isinstance(raw, list):
        raise AgendaError(400, "appointments[] attendu")
    if len(raw) > 500:
        raise AgendaError(400, "Lot trop grand (max 500)")

    created = 0
    updated = 0
    kept = 0
    for item in raw:
        o = as_object(item)
        appt_id = require_string(o, "id", max_len=64)
        est_id = require_string(o, "establishment_id", max_len=64)
        patient_name = require_string(o, "patient_name", max_len=120)
        patient_phone = optional_string(o, "patient_phone", max_len=40)
        date = require_date(o, "date")
        time = require_time(o, "time")
        duration_min = require_int(o, "duration_min", min_val=5, max_val=240)
        reason = optional_string(o, "reason", max_len=300)
        status = one_of(o, "status", STATUSES)
        source = one_of(o, "source", SOURCES, "app")
        created_at = optional_iso(o, "created_at")
        updated_at = optional_iso(o, "updated_at")
        series_id = optional_string(o, "series_id", max_len=64)
        reminder_sent_at = optional_string(o, "reminder_sent_at", max_len=40)

        now = now_iso()
        existing = session.get(Appointment, appt_id)
        if existing is None:
            session.add(
                Appointment(
                    id=appt_id,
                    doctor_id=doctor.id,
                    establishment_id=est_id,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    date=date,
                    time=time,
                    duration_min=duration_min,
                    reason=reason,
                    status=status,
                    source=source,
                    created_at=created_at or now,
                    updated_at=updated_at or now,
                    series_id=series_id,
                    reminder_sent_at=reminder_sent_at,
                )
            )
            session.commit()
            created += 1
        elif existing.doctor_id != doctor.id:
            kept += 1
        else:
            incoming = updated_at or now
            if incoming < existing.updated_at:
                kept += 1
            else:
                moved = (
                    existing.date != date
                    or existing.time != time
                    or existing.duration_min != duration_min
                )
                existing.establishment_id = est_id
                existing.patient_name = patient_name
                existing.patient_phone = patient_phone
                existing.date = date
                existing.time = time
                existing.duration_min = duration_min
                existing.reason = reason
                existing.status = status
                existing.source = source
                if "series_id" in o:
                    existing.series_id = series_id
                if moved:
                    existing.reminder_sent_at = None
                elif "reminder_sent_at" in o:
                    existing.reminder_sent_at = reminder_sent_at
                existing.updated_at = incoming
                session.commit()
                updated += 1

    return {"created": created, "updated": updated, "kept": kept, "server_time": now_iso()}
