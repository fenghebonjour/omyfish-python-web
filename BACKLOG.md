# OMyFish Python-Web — Backlog

Deferred ideas and future work. Not committed scope — parking lot for things worth doing.

Cross-repo context lives in the family alignment plan
(`/home/bigblue/.claude/plans/wondrous-shimmying-ripple.md`) — this file tracks
just python-web's slice of it.

---

## [x] A1 — Real image storage + imageStorageKey flow, route versioning

**Status:** DONE (2026-07-28, commit aad9791). django-storages + boto3
added; STORAGES config mirrors the SQLite/Postgres dev-vs-docker split
(local disk unless MINIO_ENDPOINT_URL is set); new `minio` service in
docker-compose.yml. IdentifyView persists uploads and returns a real
`imageKey`. Observation model renamed `confidence`→`top_confidence`,
`image_url`→`image_storage_key` to match the family contract exactly
(`imageUrl` is now a read-only computed field). All routes bumped to
`/api/v1/...`. Smoke-tested end to end.

This repo currently has neither piece the family decision requires — new
implementation, not just renaming:

- Add an object-storage integration to `apps/species/` (local `MEDIA_ROOT` for
  `make run`, MinIO/S3-compatible in `docker-compose.yml` — mirror the SQLite/
  Postgres dev-vs-docker split already used for the DB, see `config/settings.py`
  `DATABASES`). `IdentifyView` (`apps/species/views.py`) must persist the
  uploaded image and return a real `imageKey` instead of the synthesized
  `uuid.uuid4()` placeholder it returns today.
- Add `image_storage_key` to the `Observation` model/serializer
  (`apps/observations/models.py`, `serializers.py`) and accept it in
  `POST /api/v1/observations`, matching Java's `CreateObservationRequest`
  two-step pattern (identify persists + returns a key; create references it).
- Bump route prefixes in `config/urls.py` from `/api/auth`, `/api/notifications`,
  `/api/billing`, `/api/admin` to `/api/v1/auth`, `/api/v1/notifications`,
  `/api/v1/billing`, `/api/v1/admin` (species/observations already use
  `/api/v1/...` — this closes the last inconsistency, matching the family-wide
  versioning decision). Remember each app's `urls.py` sub-patterns need their
  leading `/` kept intact (see the `APPEND_SLASH = False` note in
  `config/settings.py`).

---

## [x] B — Proxy the Quebec Regs Advisor feature

**Status:** DONE (2026-07-28, commit 4a9cc86). Implemented at
`/api/v1/species/regs/*` — **corrected from this file's original
`/api/v1/regs/*`** to match the nesting convention Java/.NET settled on
(bite-score lives at `/species/bite-score` too). 5 proxy functions in
`ai_client.py` + 5 `AllowAny` views. Smoke-tested: correct 503s when
omyfish-ai is unreachable, 400 validation on `/ask` with no question.

---

## [x] C — Adopt the unified frontend baseline

**Status:** DONE (2026-07-29, commit 77a74b8). `frontend/omyfish-web/`
replaced wholesale with the finalized `omyfish-dotnet` baseline — dropped an
accidentally-rsynced dotnet-local `.env.local` dev override before
committing. Verified byte-identical to `omyfish-java`'s and
`omyfish-dotnet`'s copies (`diff -rq`, excluding node_modules/.next) and with
a clean `next build` in this repo.

**All workstreams for this repo are now complete.**

---

## [ ] E — Migrate species catalog persistence to MongoDB

**Status:** NOT STARTED (added 2026-08-19). `omyfish-java` did this first
(commit 36c0200, see its `BACKLOG.md` item E) — species catalog is
read-mostly, flexible-schema reference data with no relational integrity
needs, so it doesn't belong on Postgres. Port the same move here:

- `apps/species/models.py`'s `Species` is currently a plain Django ORM model
  (Postgres via the shared `DATABASE_URL`, migration
  `apps/species/migrations/0001_initial.py`). Django's ORM doesn't speak
  MongoDB natively — decide on `djongo`/`mongoengine` vs. a thin repository
  wrapping `pymongo` directly behind `apps/species`'s existing view/serializer
  boundary (`views.py`, `serializers.py`) before starting; the latter is
  closer to Java's ports-and-adapters pattern (`SpeciesDocument`/
  `SpeciesMongoRepository` behind `SpeciesRepository`) and avoids fighting
  Django's ORM/admin assumptions about a relational backend.
- Whatever adapter is chosen, `apps/species/admin.py`'s `Species` registration
  will need reworking or dropping — Django admin assumes a `Model` subclass
  backed by the ORM.
- `seed_species.py` (`apps/species/management/commands/`) currently seeds via
  the Django ORM — update it to go through the new repository/adapter
  instead, same idempotent "skip if scientific/key already exists" behavior
  Java's `SpeciesSeeder` uses.
- Add a `mongodb` service to `docker-compose.yml` (mirror Java's: `mongo:7`,
  root user/pass env vars, healthcheck via `mongosh --eval`), mirroring the
  SQLite/Postgres dev-vs-docker split already used for `DATABASES` in
  `config/settings.py` (local dev likely stays simplest with a local Mongo
  connection string rather than SQLite, since SQLite has no Mongo-equivalent
  embedded fallback).
- Verify with this repo's test suite plus an end-to-end `docker compose up
  --build` check, same as Java's verification pass.
