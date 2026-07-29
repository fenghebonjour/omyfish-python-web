# CLAUDE.md — OMyFish Python Web (Django)

## Project Family

This is the **Django full-stack member** of the OMyFish enterprise-language
family — an idiomatic Django monolith, not a microservice mirror of the
Java/.NET siblings. See `ARCHITECTURE.md` for the rationale and the full REST
contract.

- `../omyfish-python` — ML/AI origin repo; `data/metadata/fish_info.json` seeds this repo's `Species` table
- `../omyfish-ai` — standalone AI microservice, called over HTTP from `apps/species/ai_client.py`
- `../omyfish-java` — Java 21 / Spring Boot / Hexagonal, microservices
- `../omyfish-dotnet` — .NET 10 / Clean Architecture / CQRS, microservices

## Commands

```bash
make venv                # create venv + install dependencies
make run                  # migrate + runserver on :8080 (SQLite, no Docker needed)
make migrate               # apply migrations
make makemigrations         # generate migrations after model changes
make seed                  # seed Species from ../omyfish-python/data/metadata/fish_info.json
make superuser              # create a Django admin superuser
make test                  # run the test suite

make up                    # start Postgres/PostGIS + Django + frontend via Docker
make build-up               # rebuild images + start (use after code changes)
make down                   # stop all services
make shell-postgres          # psql into the omyfish DB
```

## Repository Structure

```
config/                   Django project: settings.py, urls.py, wsgi/asgi
apps/
  accounts/               Custom User (email login, role), JWT register/login/refresh
  species/                Species catalog + /identify + /bite-score + /regs (proxies omyfish-ai)
  observations/           Observation CRUD + GeoJSON (pragmatic lat/lon floats — see ARCHITECTURE.md)
  notifications/          Per-user notifications
  billing/                Subscription self-service + admin stats/subscriptions
frontend/omyfish-web/      Next.js 15 SPA, copied verbatim from omyfish-java's frontend
```

## Conventions

- All API JSON is **camelCase**; ids are string UUIDs. DRF serializers use
  explicit `source=` mappings from snake_case model fields — see
  `apps/observations/serializers.py` for the pattern.
- Auth responses (`register`/`login`/`refresh`) always return
  `{token, refreshToken, userId, email, role}` — built by
  `apps/accounts/serializers.py::auth_response`.
- `role` values are uppercase strings (`"USER"`, `"ADMIN"`) to match the
  Java/.NET siblings' convention.
- Admin-only endpoints (`apps/billing/admin_views.py`) are gated by
  `apps/billing/permissions.py::IsAdmin`, not Django's `is_staff` — that
  checks `request.user.role == "ADMIN"`.
- `AI_SERVICE_URL` (default `http://localhost:8000`) points at the standalone
  `omyfish-ai` service. `apps/species/ai_client.py::camelize()` recursively
  converts every AI response key to camelCase before it reaches the frontend.
- Database defaults to SQLite (`DATABASE_URL` unset) so `make run` needs no
  external services. Docker Compose sets `DATABASE_URL` to the Postgres/PostGIS
  container to mirror the siblings.
- Object storage defaults to local disk (`MINIO_ENDPOINT_URL` unset) for the
  same reason; Docker Compose points it at the `minio` container. `/identify`
  persists the image and returns a real key as `imageKey`; observation-create
  references it via `imageStorageKey` instead of re-uploading.
