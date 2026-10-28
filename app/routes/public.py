from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.errors import AgendaError
from app.models import Doctor, Establishment, doctor_establishments
from app.schemas import doctor_public, establishment_dict
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

router = APIRouter(tags=["reservation"])


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


BOOKING_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prise de rendez-vous — __DOCTOR_NAME__</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #f6f7f9; color: #1f2933; }
  header { background: #179F4E; color: #fff; padding: 16px; }
  header h1 { margin: 0 0 4px; font-size: 20px; }
  header p { margin: 0; font-size: 13px; opacity: .9; }
  main { padding: 16px; }
  .day { border: 1px solid #e4e7eb; background: #fff; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
  .day.selected { border-color: #179F4E; box-shadow: 0 0 0 2px #179F4E33; }
  .day .dow { font-size: 12px; color: #6b7280; text-transform: uppercase; }
  .day .date { font-weight: 600; }
  .slot { display: block; width: 100%; padding: 12px; margin-top: 8px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; font-size: 15px; text-align: left; }
  .slot.free { border-color: #179F4E; color: #179F4E; background: #179F4E0d; }
  .slot.taken { opacity: .4; text-decoration: line-through; }
  form { display: none; background: #fff; border: 1px solid #e4e7eb; border-radius: 10px; padding: 16px; }
  form.visible { display: block; }
  label { display: block; font-size: 13px; font-weight: 600; margin: 12px 0 4px; }
  input, textarea { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 15px; }
  button { width: 100%; margin-top: 16px; padding: 14px; border: 0; border-radius: 10px; background: #179F4E; color: #fff; font-size: 16px; font-weight: 700; }
  button:disabled { background: #9ca3af; }
  #error { color: #dc2626; font-size: 14px; margin-top: 8px; display: none; }
  #confirmation { display: none; background: #fff; border-radius: 10px; padding: 24px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>__DOCTOR_NAME__</h1>
  <p>Prenez rendez-vous en ligne — gratuit, sans compte</p>
</header>
<main>
  <div id="days"></div>
  <div id="slots"></div>
  <div id="form-wrap">
    <form id="booking-form" onsubmit="return false;">
      <input type="hidden" id="date" />
      <input type="hidden" id="time" />
      <input type="hidden" id="duration_min" />
      <input type="hidden" id="establishment_id" />
      <label for="patient_name">Nom complet *</label>
      <input id="patient_name" required />
      <label for="patient_phone">Téléphone *</label>
      <input id="patient_phone" type="tel" required />
      <label for="reason">Motif</label>
      <textarea id="reason" rows="2"></textarea>
      <div id="error"></div>
      <button type="submit">Confirmer le rendez-vous</button>
    </form>
    <div id="confirmation">
      <h2>RDV confirmé</h2>
      <p id="conf-detail"></p>
      <button type="button" id="reset">Prendre un autre rendez-vous</button>
    </div>
  </div>
</main>
<script>
var doctor = {doctor_json};
var establishments = {est_json};
var selectedDate = null;
var selectedSlot = null;

function isoDays(n) {
  var out = [];
  for (var i = 0; i < n; i++) {
    var d = new Date();
    d.setDate(d.getDate() + i);
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    out.push({iso: d.getFullYear() + '-' + mm + '-' + dd, label: d.toLocaleDateString('fr-FR', {weekday: 'long', day: 'numeric', month: 'long'})});
  }
  return out;
}

var daysCache = null;
function days() { if (!daysCache) daysCache = isoDays(7); return daysCache; }

function renderDays() {
  var box = document.getElementById('days');
  box.innerHTML = '';
  days().forEach(function (d, idx) {
    var el = document.createElement('div');
    el.className = 'day';
    el.innerHTML = '<div class="dow">' + d.label.split(',')[0] + '</div><div class="date">' + d.label + '</div>';
    el.onclick = function () { selectDay(d); };
    box.appendChild(el);
  });
}

function selectDay(d) {
  selectedDate = d;
  document.getElementById('slots').innerHTML = '';
  document.getElementById('form-wrap').classList.remove('visible');
  document.getElementById('confirmation').style.display = 'none';
  days().forEach(function (x, idx) { document.querySelectorAll('.day')[idx].classList.toggle('selected', x.iso === d.iso); });
  fetch('/booking/' + doctor.slug + '/slots?date=' + d.iso + '&duration=30' + (establishments.length > 1 ? '&establishment_id=' + encodeURIComponent(selectedEstId) : ''))
    .then(function (r) { return r.json(); })
    .then(function (data) { renderSlots(data.slots); })
    .catch(function () { showError('Impossible de charger les créneaux.'); });
}

function renderSlots(slots) {
  var box = document.getElementById('slots');
  box.innerHTML = '';
  if (!slots.length) { box.innerHTML = '<p>Aucun créneau disponible pour ce jour.</p>'; return; }
  slots.forEach(function (t) {
    var el = document.createElement('button');
    el.type = 'button';
    el.className = 'slot free';
    el.textContent = t;
    el.onclick = function () { chooseSlot(t); };
    box.appendChild(el);
  });
}

function chooseSlot(t) {
  selectedSlot = t;
  document.getElementById('date').value = selectedDate.iso;
  document.getElementById('time').value = t;
  document.getElementById('duration_min').value = '30';
  var estSelect = document.getElementById('establishment_id');
  if (establishments.length > 1) {
    estSelect.style.display = 'block';
    estSelect.innerHTML = '';
    establishments.forEach(function (e) {
      var o = document.createElement('option');
      o.value = e.id;
      o.textContent = e.name;
      estSelect.appendChild(o);
    });
  } else {
    estSelect.style.display = 'none';
  }
  document.getElementById('establishment_id').value = selectedEstId;
  document.getElementById('form-wrap').classList.add('visible');
}

document.getElementById('booking-form').onsubmit = function (ev) {
  ev.preventDefault();
  var payload = {
    establishment_id: document.getElementById('establishment_id').value,
    patient_name: document.getElementById('patient_name').value,
    patient_phone: document.getElementById('patient_phone').value,
    date: document.getElementById('date').value,
    time: document.getElementById('time').value,
    duration_min: 30,
    reason: document.getElementById('reason').value || null
  };
  fetch('/booking/' + doctor.slug + '/appointments', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)})
    .then(function (r) { return r.json().then(function (d) { return {status: r.status, data: d}; }); })
    .then(function (res) {
      if (res.status >= 200 && res.status < 300) {
        document.getElementById('confirmation').style.display = 'block';
        document.getElementById('conf-detail').textContent = 'RDV le ' + res.data.appointment.date + ' à ' + res.data.appointment.time + ' confirmé.';
      } else {
        showError(res.data.error || 'Erreur lors de la réservation.');
      }
    })
    .catch(function () { showError('Erreur réseau.'); });
};

document.getElementById('reset').onclick = function () {
  document.getElementById('form-wrap').classList.remove('visible');
  document.getElementById('confirmation').style.display = 'none';
  selectedSlot = null;
  selectedDate = null;
};

var selectedEstId = establishments.length ? establishments[0].id : '';

function showError(msg) {
  var el = document.getElementById('error');
  el.style.display = 'block';
  el.textContent = msg;
}

renderDays();
</script>
</body>
</html>
"""


@router.get("/b/{slug}")
def booking_page(slug: str, session: Session = Depends(get_session)):
    doctor = _require_doctor(session, slug)
    establishments = _list_establishments(session, doctor.id)
    entries = ['{"id": "%s", "name": "%s"}' % (e.id, e.name) for e in establishments]
    est_json = "[" + ",".join(entries) + "]"
    html = (
        BOOKING_HTML_TEMPLATE.replace("__DOCTOR_NAME__", doctor.name)
        .replace("{doctor_json}", '{"slug": "%s"}' % doctor.slug)
        .replace("{est_json}", est_json)
    )
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")
