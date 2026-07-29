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

## [ ] C — Adopt the unified frontend baseline

**Status:** NOT STARTED. Depends on A1 and B landing everywhere first.

This repo's `frontend/omyfish-web/` is currently a byte-identical copy of
`omyfish-java`'s (the older pattern — `lib/auth.ts` + flat `lib/api.ts`
functions, no `AuthContext`, no `/register` page). Once the unified frontend
baseline (sourced from `omyfish-dotnet`, adjusted for the family's
`token`/`refreshToken`/uppercase-role contract, with the Regs Advisor UI added)
is finalized, replace this repo's `frontend/omyfish-web/` wholesale with it —
same copy process used to create it originally.
