from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AvailabilityRule, Doctor, Establishment, doctor_establishments
from app.utils import now_iso, random_id

DEMO_DOCTOR = {
    "id": "doc-demo",
    "name": "Dr KPATCHA",
    "email": "kpatcha@liksoft.tg",
    "slug": "dr-kpatcha",
    "api_key": "demo-key-kpatcha",
}

DEMO_ESTABLISHMENTS = [
    ("est-cabinet", "Cabinet médical – Lomé", "Lomé, Togo", "#179F4E"),
    ("est-chu", "CHU de Lomé", "Tokoin, Lomé", "#2563EB"),
    ("est-clinique", "Clinique de Rappotemé", "Agoè, Lomé", "#0E7490"),
]


def seed(session: Session) -> None:
    """Données de démarrage idempotentes (mêmes ids/cls que l'app mobile)."""
    now = now_iso()

    if session.get(Doctor, DEMO_DOCTOR["id"]) is None:
        session.add(Doctor(**DEMO_DOCTOR, created_at=now))
        session.flush()

    for est_id, name, address, color in DEMO_ESTABLISHMENTS:
        if session.get(Establishment, est_id) is None:
            session.add(
                Establishment(
                    id=est_id,
                    name=name,
                    address=address,
                    color=color,
                    connector_key=f"conn-{est_id}",
                    created_at=now,
                )
            )
            session.flush()
        link = session.execute(
            select(doctor_establishments.c.doctor_id).where(
                doctor_establishments.c.doctor_id == DEMO_DOCTOR["id"],
                doctor_establishments.c.establishment_id == est_id,
            )
        ).first()
        if link is None:
            session.execute(
                doctor_establishments.insert().values(
                    doctor_id=DEMO_DOCTOR["id"], establishment_id=est_id
                )
            )

    rule_count = session.scalar(
        select(func.count())
        .select_from(AvailabilityRule)
        .where(AvailabilityRule.doctor_id == DEMO_DOCTOR["id"])
    )
    if not rule_count:
        for weekday in range(1, 7):  # lundi … samedi (0 = dimanche)
            session.add(
                AvailabilityRule(
                    id=random_id("av"),
                    doctor_id=DEMO_DOCTOR["id"],
                    establishment_id=None,
                    weekday=weekday,
                    start_at="08:00",
                    end_at="18:00",
                )
            )

    session.commit()
