"""Serialiseurs → JSON exact du contrat API.md (champs identiques à la version TS)."""

from app.models import Appointment, AvailabilityRule, Doctor, Establishment


def doctor_public(d: Doctor) -> dict:
    return {"id": d.id, "name": d.name, "email": d.email, "slug": d.slug}


def establishment_dict(e: Establishment) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "address": e.address,
        "color": e.color,
        "connector_key": e.connector_key,
        "created_at": e.created_at,
    }


def rule_dict(r: AvailabilityRule) -> dict:
    return {
        "id": r.id,
        "doctor_id": r.doctor_id,
        "establishment_id": r.establishment_id,
        "weekday": r.weekday,
        "start": r.start_at,
        "end": r.end_at,
    }


def appointment_dict(a: Appointment) -> dict:
    return {
        "id": a.id,
        "doctor_id": a.doctor_id,
        "establishment_id": a.establishment_id,
        "patient_name": a.patient_name,
        "patient_phone": a.patient_phone,
        "date": a.date,
        "time": a.time,
        "duration_min": a.duration_min,
        "reason": a.reason,
        "status": a.status,
        "source": a.source,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "series_id": a.series_id,
        "reminder_sent_at": a.reminder_sent_at,
    }
