# Agenda Central (Python / FastAPI / Docker)

API centrale d'**agenda médecin multi-établissements** — LIKSOFT.
Contrat d'API : [`API.md`](API.md) — l'app
`mobile/doctor-agenda` fonctionne telle quelle contre cette API.

Quatre espaces :

| Espace | Prefixe | Auth |
|---|---|---|
| Médecin (app mobile) | `/api` | `X-Api-Key` |
| Synchro app (local-first, LWW) | `/api/sync` | `X-Api-Key` |
| Réservation patient (public) | `/booking` | aucune (slug) |
| Connecteur SIH (LIKMED…) | `/connector` | `X-Connector-Key` |

## Stack

- Python ≥ 3.11 — FastAPI, SQLAlchemy 2, Alembic, Pydantic-settings (conventions `backend/employee-hub`)
- PostgreSQL 16 (Docker) — schéma via migrations Alembic
- pytest (36 scénarios bout en bout, `tests/test_smoke.py`)
- ruff, black, mypy — linting et type checking
- GZip middleware — compression des réponses

## Lancer avec Docker (recommandé)

```bash
cd backend/agenda-central
docker compose up -d      # db (Postgres :5435) + api (:4400, migrations + seed auto)
curl localhost:4400/health
docker compose logs -f api
docker compose down        # arrêt
```

Le seed crée à la volée : Dr KPATCHA (`demo-key-kpatcha`), 3 établissements
(`est-cabinet`/`est-chu`/`est-clinique`), dispos lun–sam 08:00–18:00.

## Lancer sans Docker (dev)

```bash
cd backend/agenda-central
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env                       # DATABASE_URL → localhost:5435
docker compose up -d db                    # juste le Postgres
.venv/bin/alembic upgrade head             # schéma
.venv/bin/uvicorn app.main:app --reload --port 4400
```

## Tests

```bash
.venv/bin/pytest        # 36 scénarios : médecin, créneaux, RDV, LWW, patient, connecteur, booking, rappels
.venv/bin/pytest --cov=app --cov-report=html  # avec coverage
```

## Linting & Formatting

```bash
./scripts/lint.sh        # vérifier le code (ruff, black, mypy)
./scripts/format.sh      # formater le code automatiquement
```

## Essais rapides

```bash
# Profil médecin
curl -H "X-Api-Key: demo-key-kpatcha" localhost:4400/api/me

# Créneaux libres d'un mardi
curl -H "X-Api-Key: demo-key-kpatcha" "localhost:4400/api/slots?date=2026-10-27&duration=30"

# Réservation publique
curl "localhost:4400/booking/dr-kpatcha/slots?date=2026-10-27"

# Page HTML autonome de réservation patient (mobile-first FR)
curl "localhost:4400/b/dr-kpatcha" | head -20

# Connecteur SIH
curl -H "X-Connector-Key: conn-est-cabinet" "localhost:4400/connector/slots?date=2026-10-27"
```

App mobile : Réglages → « Agenda central » → URL `http://10.0.2.2:4400`
(émulateur Android) ou `http://<IP-machine>:4400`, clé `demo-key-kpatcha`.

## Structure

```
agenda-central/
├── docker-compose.yml      # api (:4400) + postgres (:5435)
├── Dockerfile
├── alembic/                # migrations (versions/0001_initial.py)
├── app/
│   ├── main.py             # create_app() + /health + 404 JSON + loop rappels
│   ├── config.py           # DATABASE_URL, port, reminder_lead_min, twilio_*
│   ├── db.py               # engine/session (SQLite en test, PG en prod)
│   ├── models.py           # doctors, establishments, m2m, règles, RDV
│   ├── deps.py             # require_doctor / require_connector (headers)
│   ├── validate.py         # messages d'erreur identiques à la version TS
│   ├── slots.py            # créneaux libres + conflits (LWW inclus)
│   ├── schemas.py          # sérialisation JSON du contrat
│   ├── seed.py             # démarrage idempotent (Dr KPATCHA…)
│   ├── errors.py           # {"error": …} + codes 400/401/404/409
│   └── routes/             # doctor.py, sync.py, booking.py, connector.py, public.py
└── tests/test_smoke.py     # 36 scénarios pytest
```

## Notes d'implémentation

- Implémentation initiale en TypeScript (port 4300) supprimée : ce projet est
- Rappels serveur : task FastAPI (lifespan) + `GET /b/{slug}` (HTML patient)
- Migration `0002_series_reminders` : `series_id`, `reminder_sent_at`
  la référence unique, le contrat `API.md` a été conservé ici.
- `DELETE /api/establishments/:id` : détache le médecin (ligne conservée,
  idempotent) — 404 seulement si l'établissement n'existe pas du tout.
- `POST /api/sync/appointments` : un id déjà utilisé par **un autre médecin**
  compte `kept` au lieu d'écraser (garde-fou ajouté).
- Port Postgres hôte **5435** (5433/5434 pris par d'autres projets locaux).

## Évolutions prévues

- JWT (aujourd'hui : clés statiques)
- Rappels automatiques SMS/WhatsApp planifiés (`apscheduler`, cf. `employee-hub`)
- Webhooks vers le SIH (aujourd'hui : polling `since=`)
- Disponibilités exceptionnelles (jours fériés, blocs)

## Améliorations récentes

- **Sécurité** : CORS configurable, GZip middleware, variables d'environnement pour sécurité
- **Qualité de code** : ruff (linting), black (formatting), mypy (type checking)
- **Infrastructure** : Dockerfile multi-stage optimisé, health checks, restart policies
- **Pagination** : endpoints de liste supportent `page` et `page_size` (max 100)
- **Tests** : pytest-cov configuré, tests de pagination ajoutés
- **Logging** : configuration flexible via variables d'environnement
