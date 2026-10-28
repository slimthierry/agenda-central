"""Validateurs maison — messages identiques à la version TypeScript (API.md)."""

import json
import re

from fastapi import Request

from app.errors import AgendaError

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].*)?$")


async def read_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise AgendaError(400, "JSON invalide") from None
    return as_object(data)


def as_object(body) -> dict:
    if not isinstance(body, dict):
        raise AgendaError(400, "Corps JSON attendu")
    return body


def require_string(obj: dict, field: str, max_len: int | None = None, pattern: re.Pattern | None = None) -> str:
    v = obj.get(field)
    if not isinstance(v, str) or not v.strip():
        raise AgendaError(400, f"Champ requis : {field}")
    if max_len and len(v) > max_len:
        raise AgendaError(400, f"Champ trop long : {field}")
    if pattern and not pattern.match(v):
        raise AgendaError(400, f"Format invalide : {field}")
    return v.strip()


def optional_string(obj: dict, field: str, max_len: int | None = None) -> str | None:
    v = obj.get(field)
    if v is None or v == "":
        return None
    if not isinstance(v, str):
        raise AgendaError(400, f"Format invalide : {field}")
    if max_len and len(v) > max_len:
        raise AgendaError(400, f"Champ trop long : {field}")
    return v.strip()


def require_int(obj: dict, field: str, min_val: int | None = None, max_val: int | None = None) -> int:
    v = obj.get(field)
    n: int | None
    if isinstance(v, bool):
        n = None
    elif isinstance(v, int):
        n = v
    elif isinstance(v, float) and v.is_integer():
        n = int(v)
    elif isinstance(v, str):
        try:
            f = float(v)
        except ValueError:
            f = float("nan")
        n = int(f) if f == f and f.is_integer() else None
    else:
        n = None
    if n is None:
        raise AgendaError(400, f"Entier requis : {field}")
    if min_val is not None and n < min_val:
        raise AgendaError(400, f"Valeur trop petite : {field}")
    if max_val is not None and n > max_val:
        raise AgendaError(400, f"Valeur trop grande : {field}")
    return n


def require_date(obj: dict, field: str) -> str:
    return require_string(obj, field, pattern=DATE_RE)


def require_time(obj: dict, field: str) -> str:
    return require_string(obj, field, pattern=TIME_RE)


def optional_iso(obj: dict, field: str) -> str | None:
    v = optional_string(obj, field, max_len=40)
    if v is None:
        return None
    if not ISO_RE.match(v):
        raise AgendaError(400, f"Format ISO attendu : {field}")
    return v


def one_of(obj: dict, field: str, allowed: list[str] | tuple[str, ...], fallback: str | None = None) -> str:
    if field not in obj and fallback is not None:
        return fallback
    v = obj.get(field)
    if not isinstance(v, str) or v not in allowed:
        raise AgendaError(400, f"Valeur invalide pour {field} (attendu : {', '.join(allowed)})")
    return v
