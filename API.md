# Contrat d'API — Doctor Agenda Central

Version 1 — `http://localhost:4300`

Base : tout corps en JSON. Les erreurs répondent `{ "error": "message" }`
avec le code HTTP approprié (400 validation, 401 auth, 404 introuvable,
409 conflit de créneau).

## Authentifications

| Acteur | Mécanisme | Header |
|---|---|---|
| Médecin (app mobile) | clé API du médecin | `X-Api-Key: demo-key-kpatcha` |
| Connecteur SIH | clé par établissement | `X-Connector-Key: conn-est-cabinet` |
| Patient (web) | slug public du médecin | aucune |
| Rendez-vous | id opaque (uuid) | aucune |

## Modèle de données (simplifié)

```
Doctor          id, name, email, slug, api_key
Establishment   id, name, address, color, connector_key
Doctor↔Estab    many-to-many (médecin multi-hôpitaux)
Availability    doctor_id, establishment_id?, weekday (0=dim…6=sam), start, end
Appointment     id, doctor_id, establishment_id, patient_name, patient_phone,
                date (YYYY-MM-DD), time (HH:mm), duration_min, reason,
                status (draft|confirmed|done|canceled),
                source (app|connector|patient), created_at, updated_at
```

Les identifiants sont générés côté client pour la synchro (upsert idempotent).

---

## Santé

### `GET /health`
→ `200 { ok, service, time }`

---

## Espace médecin (app mobile)

### `GET /api/me`
→ `200 { doctor: {id,name,email,slug}, establishments: [...] }`

### `GET /api/establishments`
→ `200 { establishments: [...] }`

### `POST /api/establishments`
`{ id?, name, address?, color? }` → `201 { establishment }`

### `DELETE /api/establishments/:id` → `204`

### `GET /api/availability`
→ `200 { rules: [{id, establishment_id, weekday, start, end}] }`

### `PUT /api/availability`
`{ rules: [{establishment_id?, weekday, start, end}] }` → remplace toutes
les règles du médecin → `200 { rules }`

### `GET /api/slots?date=YYYY-MM-DD&duration=30&establishment_id=`
Créneaux **libres** (règles de disponibilité − RDV existants, chevauchements exclus).
→ `200 { date, duration_min, slots: ["08:00", "08:30", ...] }`

### `GET /api/appointments?date=&establishment_id=&status=`
→ `200 { appointments: [...] }`

### `GET /api/appointments/:id` → `200 { appointment }`

### `POST /api/appointments`
```json
{
  "id": "ap-mobile-1",              // optionnel (client)
  "establishment_id": "est-cabinet",
  "patient_name": "Afi SODJI",
  "patient_phone": "+22890000001",
  "date": "2026-10-27",
  "time": "08:30",
  "duration_min": 30,
  "reason": "Suivi",
  "status": "draft",                // défaut draft
  "source": "app"                   // défaut app
}
```
→ `201 { appointment }` — `409` si le médecin est déjà occupé.

### `PATCH /api/appointments/:id`
Champs partiels (dont `status`) → `200 { appointment }` — `409` si conflit.

### `DELETE /api/appointments/:id` → `204`

---

## Synchro app mobile (local-first)

Stratégie : **last-write-wins** sur `updated_at`, identifiants côté client.

### `GET /api/sync/appointments?since=ISO`
→ `200 { appointments: [modifiés depuis `since`], server_time }`

### `POST /api/sync/appointments`
```json
{ "appointments": [ { "id": "ap-mobile-1", "establishment_id": "...",
    "patient_name": "...", "date": "...", "time": "...", "duration_min": 30,
    "status": "draft", "source": "app", "updated_at": "ISO",
    "series_id": "ser-...", "reminder_sent_at": "ISO" } ] }
```
→ `200 { created, updated, kept, server_time }` — `kept` = version serveur plus récente.

Champs optionnels : `series_id` (identifiant de série de RDV récurrents, nullable) et
`reminder_sent_at` (RFC-3339, renseigné par le serveur après envoi du rappel). En cas de mise à
jour d'un RDV dont `date`, `time` ou `duration_min` change, le serveur remet `reminder_sent_at`
à `null` (rappel redevra partir).

---

## Réservation patient (public)

### `GET /booking/:slug/slots?date=YYYY-MM-DD&duration=30&establishment_id=`
→ `200 { doctor, date, duration_min, slots }`

### `GET /booking/:slug`
Infos publiques pour la page de réservation :
→ `200 { doctor: {id, name, email, slug}, establishments: [{id, name, address, color, connector_key, created_at}] }`

### `GET /b/:slug`
Page HTML autonome (FR, mobile-first, zéro infra) servant le parcours de réservation.
Contenu : choix date (7 jours glissants), créneaux via `GET /booking/:slug/slots`, formulaire
nom/téléphone/motif, `POST /booking/:slug/appointments`. Le médecin et les établissements sont
injectés par le serveur.

### `POST /booking/:slug/appointments`
```json
{ "establishment_id": "est-cabinet", "patient_name": "...",
  "patient_phone": "...", "date": "2026-10-27", "time": "09:00",
  "duration_min": 30, "reason": "..." }
```
→ `201 { appointment }` (`status: confirmed`, `source: patient`) — `409` si pris.

### `GET /booking/appointments/:id`
Suivi du patient → `200 { appointment }`

---

## Connecteur SIH (LIKMED / autres)

Auth : `X-Connector-Key: conn-<établissement>`.

### `GET /connector/slots?date=YYYY-MM-DD&duration=30&doctor_id=`
Créneaux libres de **tous les médecins** rattachés à l'établissement.
→ `200 { establishment, date, duration_min, doctors: [{doctor_id, doctor_name, slots}] }`

### `POST /connector/appointments`
Le SIH **pousse** son rendez-vous :
```json
{ "doctor_id": "doc-demo", "patient_name": "...", "date": "...", "time": "...",
  "duration_min": 30, "status": "confirmed" }
```
→ `201 { appointment }` (`source: connector`) — `409` conflit, `400` médecin non rattaché.

### `GET /connector/appointments?since=ISO`
Le SIH **tire** les changements (statuts mis à jour côté central).
→ `200 { appointments, server_time }`

### `PATCH /connector/appointments/:id/status`
`{ "status": "done" }` → `200 { appointment }`

---

## Évolutions prévues

- JWT (aujourd'hui : clés statiques), multi-comptes patients avec compte
- Rappels automatiques serveur (SMS/WhatsApp) planifiés sur `date/time`
- Webhooks de notification vers le SIH (aujourd'hui : polling `since=`)
- Disponibilités exceptionnelles (jours fériés, blocs)
