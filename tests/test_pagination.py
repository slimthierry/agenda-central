"""Tests de pagination des endpoints de liste."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

DOCTOR_KEY = "demo-key-kpatcha"
DATE = "2026-10-27"


@pytest.fixture(scope="module")
def client():
    app = create_app("sqlite+pysqlite:///:memory:", create_tables=True)
    with TestClient(app) as c:
        yield c


def call(client, method, path, key=False, json=None):
    h = {}
    if key:
        h["X-Api-Key"] = DOCTOR_KEY
    kwargs = {"headers": h}
    if json is not None:
        kwargs["json"] = json
    r = client.request(method, path, **kwargs)
    try:
        data = r.json()
    except ValueError:
        data = None
    return r.status_code, data


def test_pagination_default(client):
    """Test pagination avec valeurs par défaut."""
    status, data = call(client, "GET", f"/api/appointments?date={DATE}", key=True)
    assert status == 200
    assert "appointments" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert data["page"] == 1
    assert data["page_size"] == 20


def test_pagination_custom_page_size(client):
    """Test pagination avec page_size personnalisé."""
    status, data = call(client, "GET", f"/api/appointments?date={DATE}&page_size=5", key=True)
    assert status == 200
    assert data["page_size"] == 5


def test_pagination_max_page_size(client):
    """Test que page_size est limité à 100."""
    status, data = call(client, "GET", f"/api/appointments?date={DATE}&page_size=200", key=True)
    assert status == 200
    assert data["page_size"] == 100  # limité à 100


def test_pagination_page_number(client):
    """Test pagination avec numéro de page."""
    status, data = call(client, "GET", f"/api/appointments?date={DATE}&page=2", key=True)
    assert status == 200
    assert data["page"] == 2
