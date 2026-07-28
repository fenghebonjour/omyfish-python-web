# OMyFish Python-Web — Backlog

Deferred ideas and future work. Not committed scope — parking lot for things worth doing.

Cross-repo context lives in the family alignment plan
(`/home/bigblue/.claude/plans/wondrous-shimmying-ripple.md`) — this file tracks
just python-web's slice of it.

---

## [ ] A1 — Real image storage + imageStorageKey flow, route versioning

**Status:** NOT STARTED. Blocks the frontend unification work (Workstream C).

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

## [ ] B — Proxy the Quebec Regs Advisor feature

**Status:** NOT STARTED. Depends on A1's route versioning landing first.

All chatbot/retrieval logic lives in `omyfish-ai` (frozen) at `/regs/*`
(`GET /limits`, `GET /zones/geojson`, `GET /consumption/stations`,
`GET /consumption`, `POST /ask`). Add proxy functions to
`apps/species/ai_client.py` (or a new `apps/regs/` app if it grows past a
handful of view functions) for the 5 endpoints, reusing the existing
`camelize()` recursive key-mapping helper. New views/urls under
`/api/v1/regs/*`.

---

## [ ] C — Adopt the unified frontend baseline

**Status:** NOT STARTED. Depends on A1 and B landing everywhere first.

This repo's `frontend/omyfish-web/` is currently a byte-identical copy of
`omyfish-java`'s (the older pattern — `lib/auth.ts` + flat `lib/api.ts`
functions, no `AuthContext`, no `/register` page). Once the unified frontend
baseline (sourced from `omyfish-dotnet`, adjusted for the family's
`token`/`refreshToken`/uppercase-role contract, with the Regs Advisor UI added)
is finalized, replace this repo's `frontend/omyfish-web/` wholesale with it —
same copy process used to create it originally.
