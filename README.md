# OMyFish — Python Web (Django)

Full-stack web member of the OMyFish enterprise-language family — a Django/DRF
monolith exposing the same REST contract as the `omyfish-java` and
`omyfish-dotnet` siblings, reusing their Next.js frontend verbatim.

## Project Family

- `../omyfish-python` — ML/AI origin (training, Streamlit, FastAPI)
- `../omyfish-ai` — standalone AI microservice shared by all enterprise members
- `../omyfish-java` — Java 21 / Spring Boot / Hexagonal, microservices
- `../omyfish-dotnet` — .NET 10 / Clean Architecture / CQRS, microservices
- `omyfish-python-web` (this repo) — Django monolith, single-origin DRF API

See `ARCHITECTURE.md` for the "why Django instead of microservices" rationale.

## Commands

```bash
make venv                # create venv + install dependencies
make run                 # migrate + runserver on :8080 (SQLite, no Docker needed)
make migrate             # apply migrations
make makemigrations      # generate migrations after model changes
make seed                # seed the Species table from ../omyfish-python/data/metadata/fish_info.json
make superuser           # create a Django admin superuser
make test                # run the test suite

make up                  # start Postgres/PostGIS + Django + frontend via Docker
make build-up            # rebuild images + start (use after code changes)
make down                # stop all services
make shell-postgres      # psql into the omyfish DB
```

Standalone AI service: `cd ../omyfish-ai && docker compose up -d` (or run
`docker compose --profile bundled up -d` here for a self-contained demo).

## Repository Structure

```
config/                  Django project (settings, urls, wsgi/asgi)
apps/
  accounts/              Custom User (email login), JWT register/login/refresh
  species/               Species catalog, /identify + /bite-score (proxies omyfish-ai)
  observations/           Observation CRUD + GeoJSON
  notifications/          User notifications
  billing/                Subscription (me/checkout) + admin stats/subscriptions
frontend/omyfish-web/     Next.js 15 SPA (copied verbatim from the siblings)
```

## REST Contract

All JSON is camelCase; ids are string UUIDs. See `ARCHITECTURE.md` for the
full endpoint list and the Django-replaces-api-gateway rationale.
