"""Test de bout en bout — scénarios du smoke initial (implémentation TS supprimée).

Base SQLite en mémoire, données de démarrage seedées au démarrage du TestClient.
    pytest
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

DOCTOR_KEY = "demo-key-kpatcha"
CONNECTOR_KEY = "conn-est-cabinet"
DATE = "2026-10-27"  # mardi (règles lun–sam 08:00–18:00)


@pytest.fixture(scope="module")
def client():
    app = create_app("sqlite+pysqlite:///:memory:", create_tables=True)
    with TestClient(app) as c:
        yield c


def call(client, method, path, key=False, conn=None, json=None, headers=None, content=None):
    h = dict(headers or {})
    if key:
        h["X-Api-Key"] = DOCTOR_KEY
    if conn:
        h["X-Connector-Key"] = conn
    kwargs = {"headers": h}
    if json is not None:
        kwargs["json"] = json
    if content is not None:
        kwargs["content"] = content
        kwargs["headers"] = {**h, "Content-Type": "application/json"}
    r = client.request(method, path, **kwargs)
    try:
        data = r.json()
    except ValueError:
        data = None
    return r.status_code, data


# ---------- Santé & auth ----------


def test_01_health(client):
    status, data = call(client, "GET", "/health")
    assert status == 200
    assert data["ok"] is True
    assert data["service"] == "agenda-central"
    assert data["time"].endswith("Z")


def test_02_route_inconnue(client):
    status, data = call(client, "GET", "/route-inconnue")
    assert status == 404
    assert data == {"error": "Route inconnue"}


def test_03_mauvaise_methode(client):
    status, data = call(client, "POST", "/health")
    assert status == 404
    assert data == {"error": "Route inconnue"}


def test_04_me_sans_cle(client):
    status, data = call(client, "GET", "/api/me")
    assert status == 401
    assert data == {"error": "Header X-Api-Key manquant"}


def test_05_me_cle_invalide(client):
    status, data = call(client, "GET", "/api/me", headers={"X-Api-Key": "faux"})
    assert status == 401
    assert data == {"error": "Clé API invalide"}


def test_06_me(client):
    status, data = call(client, "GET", "/api/me", key=True)
    assert status == 200
    assert data["doctor"] == {
        "id": "doc-demo",
        "name": "Dr KPATCHA",
        "email": "kpatcha@liksoft.tg",
        "slug": "dr-kpatcha",
    }
    ids = {e["id"] for e in data["establishments"]}
    assert ids == {"est-cabinet", "est-chu", "est-clinique"}
    assert data["establishments"][0]["connector_key"].startswith("conn-")


# ---------- Créneaux ----------


def test_07_slots(client):
    status, data = call(client, "GET", f"/api/slots?date={DATE}&duration=30", key=True)
    assert status == 200
    assert data["date"] == DATE
    assert data["duration_min"] == 30
    assert len(data["slots"]) == 20  # 08:00 → 17:30 par pas de 30 min
    assert data["slots"][0] == "08:00"


def test_08_slots_validations(client):
    status, data = call(client, "GET", "/api/slots?duration=30", key=True)
    assert (status, data["error"]) == (400, "Champ requis : date")
    status, data = call(client, "GET", "/api/slots?date=27-10-2026", key=True)
    assert (status, data["error"]) == (400, "Format invalide : date")
    status, data = call(client, "GET", f"/api/slots?date={DATE}&duration=abc", key=True)
    assert (status, data["error"]) == (400, "duration invalide")
    status, data = call(client, "GET", f"/api/slots?date={DATE}&duration=0", key=True)
    assert (status, data["error"]) == (400, "duration invalide")


# ---------- Rendez-vous médecin ----------


def test_09_create_appointment(client):
    status, data = call(
        client,
        "POST",
        "/api/appointments",
        key=True,
        json={
            "id": "ap-smoke-1",
            "establishment_id": "est-cabinet",
            "patient_name": "Test SMOKY",
            "patient_phone": "+22890000000",
            "date": DATE,
            "time": "08:00",
            "duration_min": 30,
            "reason": "Consultation test",
        },
    )
    assert status == 201
    a = data["appointment"]
    assert a["id"] == "ap-smoke-1"
    assert a["doctor_id"] == "doc-demo"
    assert a["status"] == "draft"
    assert a["source"] == "app"
    assert a["created_at"] == a["updated_at"]


def test_10_create_conflict(client):
    status, data = call(
        client,
        "POST",
        "/api/appointments",
        key=True,
        json={
            "establishment_id": "est-chu",
            "patient_name": "Doublon",
            "date": DATE,
            "time": "08:15",
            "duration_min": 30,
        },
    )
    assert status == 409
    assert data == {"error": "Créneau déjà occupé pour ce médecin"}


def test_11_create_validations(client):
    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"establishment_id": "est-cabinet", "date": DATE, "time": "08:00", "duration_min": 30},
    )
    assert (status, data["error"]) == (400, "Champ requis : patient_name")
    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"establishment_id": "est-cabinet", "patient_name": "X", "date": "27-10-2026",
              "time": "08:00", "duration_min": 30},
    )
    assert (status, data["error"]) == (400, "Format invalide : date")
    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"establishment_id": "est-cabinet", "patient_name": "X", "date": DATE,
              "time": "25:00", "duration_min": 30},
    )
    assert (status, data["error"]) == (400, "Format invalide : time")
    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"establishment_id": "est-cabinet", "patient_name": "X", "date": DATE,
              "time": "16:00", "duration_min": 3},
    )
    assert (status, data["error"]) == (400, "Valeur trop petite : duration_min")
    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"establishment_id": "est-cabinet", "patient_name": "X", "date": DATE,
              "time": "16:00", "duration_min": 30, "status": "busy"},
    )
    assert status == 400
    assert data["error"].startswith("Valeur invalide pour status")


def test_12_list_and_get(client):
    status, data = call(client, "GET", f"/api/appointments?date={DATE}", key=True)
    assert status == 200
    assert [a["id"] for a in data["appointments"]] == ["ap-smoke-1"]

    status, data = call(client, "GET", "/api/appointments/ap-smoke-1", key=True)
    assert status == 200
    assert data["appointment"]["patient_name"] == "Test SMOKY"

    status, data = call(client, "GET", "/api/appointments/ap-inconnu", key=True)
    assert (status, data) == (404, {"error": "Rendez-vous introuvable"})

    status, data = call(client, "GET", "/api/appointments", conn=CONNECTOR_KEY)
    assert status == 401


def test_13_patch_status(client):
    status, data = call(client, "PATCH", "/api/appointments/ap-smoke-1", key=True, json={"status": "confirmed"})
    assert status == 200
    assert data["appointment"]["status"] == "confirmed"


def test_14_delete_appointment(client):
    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"id": "ap-del-1", "establishment_id": "est-cabinet", "patient_name": "À supprimer",
              "date": DATE, "time": "16:00", "duration_min": 30},
    )
    assert status == 201
    status, _ = call(client, "DELETE", "/api/appointments/ap-del-1", key=True)
    assert status == 204
    status, data = call(client, "GET", "/api/appointments/ap-del-1", key=True)
    assert status == 404


# ---------- Synchro app mobile ----------


def test_15_sync_push_created(client):
    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{
            "id": "ap-mobile-1",
            "establishment_id": "est-chu",
            "patient_name": "Patient Mobile",
            "date": DATE,
            "time": "10:00",
            "duration_min": 20,
            "status": "draft",
            "source": "app",
            "updated_at": "2026-10-26T10:00:00.000Z",
        }]},
    )
    assert status == 200
    assert data["created"] == 1
    assert data["updated"] == 0
    assert data["kept"] == 0
    assert data["server_time"].endswith("Z")


def test_16_sync_push_stale_kept(client):
    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{
            "id": "ap-smoke-1",
            "establishment_id": "est-cabinet",
            "patient_name": "Test SMOKY",
            "date": DATE,
            "time": "08:00",
            "duration_min": 30,
            "status": "draft",
            "source": "app",
            "updated_at": "2000-01-01T00:00:00.000Z",
        }]},
    )
    assert status == 200
    assert (data["created"], data["updated"], data["kept"]) == (0, 0, 1)


def test_17_sync_push_fresher_updated(client):
    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{
            "id": "ap-mobile-1",
            "establishment_id": "est-chu",
            "patient_name": "Patient Mobile (MAJ)",
            "date": DATE,
            "time": "10:00",
            "duration_min": 20,
            "status": "confirmed",
            "source": "app",
            "updated_at": "2026-10-26T12:00:00.000Z",
        }]},
    )
    assert status == 200
    assert (data["created"], data["updated"], data["kept"]) == (0, 1, 0)


def test_18_sync_pull(client):
    status, data = call(client, "GET", "/api/sync/appointments?since=1970-01-01T00:00:00.000Z", key=True)
    assert status == 200
    by_id = {a["id"]: a for a in data["appointments"]}
    assert set(by_id) == {"ap-smoke-1", "ap-mobile-1"}
    assert by_id["ap-smoke-1"]["status"] == "confirmed"  # le stale n'a pas écrasé
    assert by_id["ap-mobile-1"]["status"] == "confirmed"  # LWW : fraîcheur appliquée
    assert by_id["ap-mobile-1"]["patient_name"] == "Patient Mobile (MAJ)"

    status, data = call(client, "GET", "/api/sync/appointments?since=2999-01-01T00:00:00.000Z", key=True)
    assert status == 200
    assert data["appointments"] == []  # strictement après `since`


def test_19_sync_validations(client):
    status, data = call(client, "POST", "/api/sync/appointments", key=True, json={})
    assert (status, data["error"]) == (400, "appointments[] attendu")
    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{"patient_name": "sans id"}]},
    )
    assert (status, data["error"]) == (400, "Champ requis : id")
    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{"id": "x", "establishment_id": "est-cabinet",
                                "patient_name": "X", "date": DATE, "time": "07:00",
                                "duration_min": 30, "status": "draft",
                                "updated_at": "not-a-date"}]},
    )
    assert (status, data["error"]) == (400, "Format ISO attendu : updated_at")
    status, data = call(client, "POST", "/api/sync/appointments", key=True, content="{json cassé")
    assert (status, data["error"]) == (400, "JSON invalide")


def test_20_patch_slot_conflict(client):
    # ap-smoke-1 (08:00) ne peut pas bouger sur ap-mobile-1 (10:00)
    status, data = call(client, "PATCH", "/api/appointments/ap-smoke-1", key=True, json={"time": "10:00"})
    assert status == 409
    # mais rester sur son propre créneau l'autorise (exclusion de soi)
    status, data = call(client, "PATCH", "/api/appointments/ap-smoke-1", key=True, json={"time": "08:00"})
    assert status == 200
    # un rendez-vous annulé n'occupe plus le créneau
    status, data = call(client, "PATCH", "/api/appointments/ap-mobile-1", key=True, json={"status": "canceled"})
    assert status == 200
    status, data = call(client, "PATCH", "/api/appointments/ap-smoke-1", key=True, json={"time": "10:00"})
    assert status == 200
    # restaure la position de départ pour les tests suivants
    call(client, "PATCH", "/api/appointments/ap-smoke-1", key=True, json={"time": "08:00"})
    call(client, "PATCH", "/api/appointments/ap-mobile-1", key=True, json={"status": "confirmed"})


# ---------- Réservation patient ----------


def test_21_booking_slots(client):
    status, data = call(client, "GET", f"/booking/dr-kpatcha/slots?date={DATE}&duration=30")
    assert status == 200
    assert data["doctor"]["slug"] == "dr-kpatcha"
    assert "08:00" not in data["slots"]  # occupé par ap-smoke-1
    assert "09:00" in data["slots"]


def test_22_booking_create_and_track(client):
    status, data = call(
        client, "POST", "/booking/dr-kpatcha/appointments",
        json={"establishment_id": "est-cabinet", "patient_name": "Patient Web",
              "patient_phone": "+22891111111", "date": DATE, "time": "09:00",
              "duration_min": 30},
    )
    assert status == 201
    a = data["appointment"]
    assert a["status"] == "confirmed"
    assert a["source"] == "patient"
    bk_id = a["id"]

    status, data = call(client, "GET", f"/booking/appointments/{bk_id}")
    assert status == 200
    assert data["appointment"]["patient_name"] == "Patient Web"


def test_23_booking_conflict(client):
    status, data = call(
        client, "POST", "/booking/dr-kpatcha/appointments",
        json={"establishment_id": "est-cabinet", "patient_name": "Tardif",
              "date": DATE, "time": "09:15", "duration_min": 30},
    )
    assert status == 409
    assert "pris" in data["error"]


def test_24_booking_404(client):
    status, data = call(client, "GET", "/booking/dr-inconnu/slots?date=" + DATE)
    assert (status, data) == (404, {"error": "Médecin introuvable"})
    status, data = call(client, "GET", "/booking/appointments/ap-inconnu")
    assert (status, data) == (404, {"error": "Rendez-vous introuvable"})


# ---------- Connecteur SIH ----------


def test_25_connector_auth(client):
    status, data = call(client, "GET", f"/connector/slots?date={DATE}")
    assert (status, data) == (401, {"error": "Header X-Connector-Key manquant"})
    status, data = call(client, "GET", f"/connector/slots?date={DATE}", conn="conn-faux")
    assert (status, data) == (401, {"error": "Clé de connecteur invalide"})


def test_26_connector_slots(client):
    status, data = call(client, "GET", f"/connector/slots?date={DATE}&duration=30", conn=CONNECTOR_KEY)
    assert status == 200
    assert data["establishment"] == {"id": "est-cabinet", "name": "Cabinet médical – Lomé"}
    assert len(data["doctors"]) == 1
    doc = data["doctors"][0]
    assert doc["doctor_id"] == "doc-demo"
    assert "08:00" not in doc["slots"]  # occupé
    assert "09:00" not in doc["slots"]  # réservation patient
    assert "14:00" in doc["slots"]

    status, data = call(client, "GET", f"/connector/slots?date={DATE}&doctor_id=doc-demo", conn=CONNECTOR_KEY)
    assert status == 200 and len(data["doctors"]) == 1
    status, data = call(client, "GET", f"/connector/slots?date={DATE}&doctor_id=doc-autre", conn=CONNECTOR_KEY)
    assert status == 200 and data["doctors"] == []


def test_27_connector_push_and_pull(client):
    status, data = call(
        client, "POST", "/connector/appointments", conn=CONNECTOR_KEY,
        json={"doctor_id": "doc-demo", "patient_name": "Depuis SIH",
              "date": DATE, "time": "14:00", "duration_min": 30, "status": "confirmed"},
    )
    assert status == 201
    a = data["appointment"]
    assert a["source"] == "connector"
    assert a["establishment_id"] == "est-cabinet"
    conn_id = a["id"]

    status, data = call(client, "GET", "/connector/appointments?since=1970-01-01T00:00:00.000Z", conn=CONNECTOR_KEY)
    assert status == 200
    pulled = {a["id"] for a in data["appointments"]}
    assert conn_id in pulled
    assert "ap-mobile-1" not in pulled  # appartient à est-chu

    status, data = call(client, "PATCH", f"/connector/appointments/{conn_id}/status",
                        conn=CONNECTOR_KEY, json={"status": "done"})
    assert status == 200
    assert data["appointment"]["status"] == "done"


def test_28_connector_errors(client):
    status, data = call(
        client, "POST", "/connector/appointments", conn=CONNECTOR_KEY,
        json={"doctor_id": "doc-inconnu", "patient_name": "X",
              "date": DATE, "time": "15:00", "duration_min": 30},
    )
    assert (status, data["error"]) == (400, "Médecin non rattaché à cet établissement")

    status, data = call(
        client, "POST", "/connector/appointments", conn=CONNECTOR_KEY,
        json={"doctor_id": "doc-demo", "patient_name": "X",
              "date": DATE, "time": "14:15", "duration_min": 30},
    )
    assert status == 409

    status, data = call(client, "PATCH", "/connector/appointments/ap-inconnu/status",
                        conn=CONNECTOR_KEY, json={"status": "done"})
    assert (status, data) == (404, {"error": "Rendez-vous introuvable"})

    # le connecteur du CHU ne touche pas aux RDV du cabinet
    status, data = call(client, "PATCH", "/connector/appointments/ap-smoke-1/status",
                        conn="conn-est-chu", json={"status": "done"})
    assert (status, data) == (404, {"error": "Rendez-vous introuvable"})

    status, data = call(client, "GET", f"/connector/slots?date={DATE}", conn="conn-est-chu")
    assert status == 200
    assert data["establishment"]["id"] == "est-chu"


# ---------- Disponibilités ----------


def test_29_availability(client):
    status, data = call(client, "GET", "/api/availability", key=True)
    assert status == 200
    assert len(data["rules"]) == 6
    assert {r["weekday"] for r in data["rules"]} == {1, 2, 3, 4, 5, 6}
    assert data["rules"][0]["start"] == "08:00"

    status, data = call(
        client, "PUT", "/api/availability", key=True,
        json={"rules": [
            {"weekday": 1, "start": "09:00", "end": "17:00"},
            {"establishment_id": "est-cabinet", "weekday": 3, "start": "08:00", "end": "12:00"},
        ]},
    )
    assert status == 200
    assert len(data["rules"]) == 2
    assert data["rules"][0]["start"] == "09:00"

    status, data = call(client, "PUT", "/api/availability", key=True, json={"rules": "non"})
    assert (status, data["error"]) == (400, "rules[] attendu")
    status, data = call(
        client, "PUT", "/api/availability", key=True,
        json={"rules": [{"weekday": 9, "start": "09:00", "end": "17:00"}]},
    )
    assert (status, data["error"]) == (400, "Valeur trop grande : weekday")
    status, data = call(
        client, "PUT", "/api/availability", key=True,
        json={"rules": [{"weekday": 1, "start": "17:00", "end": "09:00"}]},
    )
    assert (status, data["error"]) == (400, "start doit précéder end")

    # restaure lun–sam 08–18 pour l'état final
    status, data = call(
        client, "PUT", "/api/availability", key=True,
        json={"rules": [{"weekday": w, "start": "08:00", "end": "18:00"} for w in range(1, 7)]},
    )
    assert status == 200 and len(data["rules"]) == 6


# ---------- Établissements ----------


def test_30_establishments_crud(client):
    status, data = call(client, "GET", "/api/establishments", key=True)
    assert status == 200
    assert len(data["establishments"]) == 3

    status, data = call(
        client, "POST", "/api/establishments", key=True,
        json={"id": "est-test", "name": "Polygone test", "address": "Lomé", "color": "#123456"},
    )
    assert status == 201
    est = data["establishment"]
    assert est["id"] == "est-test"
    assert est["connector_key"] == "conn-est-test"
    assert est["color"] == "#123456"

    status, data = call(client, "GET", "/api/establishments", key=True)
    assert len(data["establishments"]) == 4

    status, data = call(
        client, "POST", "/api/establishments", key=True, json={"id": "est-test", "name": "Encore"},
    )
    assert status == 409

    status, data = call(client, "GET", "/api/me", key=True)
    assert any(e["id"] == "est-test" for e in data["establishments"])

    status, _ = call(client, "DELETE", "/api/establishments/est-test", key=True)
    assert status == 204
    # idempotent : seul le rattachement médecin est retiré, la ligne établissement reste
    status, _ = call(client, "DELETE", "/api/establishments/est-test", key=True)
    assert status == 204

    status, data = call(client, "GET", "/api/establishments", key=True)
    assert len(data["establishments"]) == 3


def test_31_establishment_validations(client):
    status, data = call(client, "POST", "/api/establishments", key=True, json={"name": ""})
    assert (status, data["error"]) == (400, "Champ requis : name")
    status, data = call(client, "POST", "/api/establishments", key=True, json={})
    assert (status, data["error"]) == (400, "Champ requis : name")
    status, data = call(client, "DELETE", "/api/establishments/est-jamais", key=True)
    assert (status, data) == (404, {"error": "Établissement introuvable"})


# ---------- Phase 1 — Page booking / series / rappels ----------


def test_32_booking_page_html(client):
    r = client.get("/b/dr-kpatcha")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Dr KPATCHA" in r.text
    assert "<!DOCTYPE html>" in r.text


def test_33_booking_page_unknown(client):
    status, data = call(client, "GET", "/b/dr-inconnu")
    assert (status, data) == (404, {"error": "Médecin introuvable"})


def test_34_booking_info(client):
    status, data = call(client, "GET", "/booking/dr-kpatcha")
    assert status == 200
    assert data["doctor"]["slug"] == "dr-kpatcha"
    assert len(data["establishments"]) > 0


def test_35_sync_series_and_reminder_fields(client):
    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{
            "id": "ap-series-1",
            "establishment_id": "est-cabinet",
            "patient_name": "Serie Patient",
            "date": DATE,
            "time": "13:00",
            "duration_min": 30,
            "status": "confirmed",
            "source": "app",
            "updated_at": "2026-10-26T10:00:00.000Z",
            "series_id": "ser-1",
            "reminder_sent_at": None,
        }]},
    )
    assert data["created"] == 1

    status, data = call(client, "GET", "/api/sync/appointments?since=1970-01-01T00:00:00.000Z", key=True)
    appt = [a for a in data["appointments"] if a["id"] == "ap-series-1"][0]
    assert appt["series_id"] == "ser-1"
    assert appt["reminder_sent_at"] is None

    status, data = call(
        client, "POST", "/api/sync/appointments", key=True,
        json={"appointments": [{
            "id": "ap-series-1",
            "establishment_id": "est-cabinet",
            "patient_name": "Serie Patient",
            "date": "2026-10-28",
            "time": "13:00",
            "duration_min": 30,
            "status": "confirmed",
            "source": "app",
            "updated_at": "2026-10-27T09:00:00.000Z",
            "series_id": "ser-1",
            "reminder_sent_at": "2026-10-27T08:00:00.000Z",
        }]},
    )
    assert data["updated"] == 1

    status, data = call(client, "GET", "/api/sync/appointments?since=1970-01-01T00:00:00.000Z", key=True)
    appt = [a for a in data["appointments"] if a["id"] == "ap-series-1"][0]
    # le changement de date a reset le rappel
    assert appt["reminder_sent_at"] is None


def test_36_reminder_sent_once(client, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.reminders import process_due

    async def fake_send(appt):
        fake_send.calls.append(appt.id)
        return True

    fake_send.calls = []
    monkeypatch.setattr("app.reminders.send_reminder", fake_send)

    nowdt = datetime.now(timezone.utc)
    start = nowdt + timedelta(minutes=30)
    rdv_date = start.strftime("%Y-%m-%d")
    rdv_time = start.strftime("%H:%M")

    status, data = call(
        client, "POST", "/api/appointments", key=True,
        json={"id": "ap-rem-1", "establishment_id": "est-cabinet", "patient_name": "Reminder Patient",
              "patient_phone": "+22892222222", "date": rdv_date, "time": rdv_time,
              "duration_min": 30, "status": "confirmed"},
    )
    assert status == 201

    factory = client.app.state.sessionmaker

    def run_due():
        import asyncio

        with factory() as session:
            return asyncio.run(process_due(session))

    assert run_due() == ["ap-rem-1"]
    assert run_due() == []
    assert len(fake_send.calls) == 1

    status, _ = call(client, "DELETE", "/api/appointments/ap-rem-1", key=True)
    assert status == 204
