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

---

## [x] F — Regs & Tips: render chat answers as Markdown, not raw text

**Status:** DONE (2026-08-25, commit 88503de). `/regs/ask` returns
Groq-generated Markdown (bold, bullet lists, etc.), but the shared
frontend's chat UI dumped it into plain text, so users saw literal
`**`/`-` characters. Fixed via `react-markdown` — same bug independently
found and fixed the same day in `omyfish-java` (commit e510503) and
`omyfish-dotnet` (commit 4e7e38b), expected since all three share
`frontend/omyfish-web` byte-for-byte (item C above). `omyfish-ios` has its
own separate SwiftUI chat view and carried the same bug until 2026-08-28
(commit e53b418), fixed there via `AttributedString(markdown:)`.

---

## [~] G — Weakness audit follow-up (ported from omyfish-dotnet)

**Status:** IN PROGRESS (added 2026-09-11). `omyfish-dotnet` went through a
senior-dev-style weakness audit (its `BACKLOG.md` item F) covering security,
resilience, data-layer, and testing/CI findings, then asked for the same
treatment across the other enterprise siblings. Full explanation in
`docs/WEAKNESS_AUDIT.md` — this file is the "what shipped". This repo is a
Django monolith, not a microservices mirror, so several dotnet findings
don't apply the same way (or at all) — each is annotated below.

**Security — DONE 2026-09-11:**
- ~~No rate limiting on `/identify`/`/bite-score/*`~~ — fixed: DRF
  `ScopedRateThrottle`, same rates as dotnet (`identify`: 10/min,
  `bite-score`: 30/min). (`WEAKNESS_AUDIT.md` §1.2)
- ~~Refresh token in response body + `localStorage`~~ — fixed: httpOnly,
  `SameSite=Strict` cookie scoped to `/api/v1/auth`, matching dotnet's
  shape exactly; added `POST /api/v1/auth/logout`. Needed
  `CORS_ALLOW_CREDENTIALS = True` as a companion change (confirmed safe
  with `CORS_ALLOW_ALL_ORIGINS = True` — see the audit doc). Frontend
  (`AuthContext.tsx`/`api.ts`) updated to match dotnet's already-shipped
  version. Verified live (register/login/refresh/logout cookie behavior)
  plus 9 new tests in `apps/accounts/tests.py`. (§1.3)
- ~~Backend container runs as root~~ — fixed: `USER django` in the root
  `Dockerfile`, mirroring what `frontend/omyfish-web/Dockerfile` (shared
  with the siblings) already did. Verified via `docker run --rm
  --entrypoint id`. No Helm/K8s manifests exist in this repo (docker-compose
  only), so that half of the dotnet finding doesn't apply. (§1.4)
- §1.1 (gateway configures auth but doesn't enforce it) — not applicable,
  already correct by construction (secure-by-default `DEFAULT_PERMISSION_CLASSES`,
  no separate gateway to desync from it).

**Resilience — DONE 2026-09-11 (bar circuit breaker, deliberate):**
- ~~AI-client retry~~ — fixed: `apps/species/ai_client.py` gained a
  module-level `requests.Session()` with a `urllib3.util.Retry` (2 retries,
  exponential backoff, retries on 502/503/504) mounted via `HTTPAdapter`;
  all seven call sites now go through the session instead of bare
  `requests.get`/`.post`. Timeouts were already present. No circuit breaker
  added — matches the dotnet/java siblings' own decision to ship
  timeout+retry first. (§2.1)
- ~~No centralized exception handling~~ — fixed: `config/exception_handler.py`
  wraps DRF's default handler, normalizing any truly unhandled exception into
  a structured 500 instead of Django's raw error page (which leaks stack
  traces whenever `DEBUG=True`, its default). (§2.2)
- §2.3/§2.4 (outbox pattern / consumer idempotency) — not applicable,
  confirmed structurally: no message broker, no Django signals, nothing that
  does two related writes needing to be coupled.

**Data layer:** all four items (§3.1–§3.4) already fine — no fixes needed.
See `WEAKNESS_AUDIT.md` for the evidence (Django's migration framework has
no schema-drift failure mode; no dead PostGIS infra exists since the geo
upgrade is a documented not-yet-done tradeoff, not an abandoned build; no
N+1 queries found).

**Testing/CI — partially done:**
- ~~Zero real tests~~ — partially fixed: `apps/accounts/tests.py` now has
  `AuthFlowTests` + `PermissionDefaultTests` (9 tests) covering the security
  fixes above. **Still open**: no tests for `apps/species`,
  `apps/observations`, `apps/notifications`, `apps/billing`.
- No CI workflow of any kind (`.github/workflows/` doesn't exist) — **not
  done**, left as a follow-up.

**Not done in this pass, left for a follow-up round:**
- Full test coverage for `apps/species`/`observations`/`notifications`/`billing`.
- A CI workflow (at minimum: `python manage.py test`, ideally + lint/format
  + frontend build + dependency scan, matching the dotnet sibling's `ci.yml`).
- Bonus findings from the audit doc: `Notification` model has no producer
  anywhere (dead write-side); `DEBUG`/`SECRET_KEY`/`JWT_SECRET` all have
  insecure dev-fallback defaults that don't fail closed in production.
