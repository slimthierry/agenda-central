from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AgendaError
from app.models import Doctor, Establishment


def get_session(request: Request):
    factory = request.app.state.sessionmaker
    session = factory()
    try:
        yield session
    finally:
        session.close()


def require_doctor(
    request: Request,
    session: Session = Depends(get_session),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
) -> Doctor:
    if not x_api_key:
        raise AgendaError(401, "Header X-Api-Key manquant")
    doctor = session.scalar(select(Doctor).where(Doctor.api_key == x_api_key))
    if doctor is None:
        raise AgendaError(401, "Clé API invalide")
    request.state.doctor = doctor
    return doctor


def require_connector(
    request: Request,
    session: Session = Depends(get_session),
    x_connector_key: str | None = Header(default=None, alias="X-Connector-Key"),
) -> Establishment:
    if not x_connector_key:
        raise AgendaError(401, "Header X-Connector-Key manquant")
    establishment = session.scalar(
        select(Establishment).where(Establishment.connector_key == x_connector_key)
    )
    if establishment is None:
        raise AgendaError(401, "Clé de connecteur invalide")
    request.state.establishment = establishment
    return establishment
