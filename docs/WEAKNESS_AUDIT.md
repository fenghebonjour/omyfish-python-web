# OMyFish Python Web — Weakness Audit (learning notes)

Ported from `omyfish-dotnet/docs/WEAKNESS_AUDIT.md`'s senior-dev-style review
(2026-09-10) — see that file for the original writeup and fix snippets. This
repo is a Django monolith, not a microservices mirror (see `CLAUDE.md`), so
several dotnet findings translate differently or don't apply at all; each
entry below says which. Tracked for real work in `BACKLOG.md` item G — this
file is the "why", that file is the "what to do".

---

## 1. Security

**Status: fixed and verified 2026-09-11** for the three items that applied
(§1.2, §1.3, §1.4-backend). §1.1 was already fine.

### 1.1 Auth enforcement — already fine

**Not applicable — already correct.** dotnet's bug was a gateway that
configured JWT auth but never called `.RequireAuthorization()`, so every
route was reachable with no token. This repo has no separate gateway to
desync from its own config: `config/settings.py`'s
`REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` defaults every view to
`IsAuthenticated`, and the genuinely public views (auth register/login/
refresh, the species catalog/identify/bite-score/regs proxies) opt out
explicitly with `permission_classes = [AllowAny]`. There's no second layer
that could quietly disagree with the first.

### 1.2 No rate limiting on `/identify` and `/bite-score/*`

**Problem:** `IdentifyView`, `BiteScoreTodayView`, `BiteScoreForecastView`
are `AllowAny` and drive cost on the external AI service, but
`config/settings.py` had no `DEFAULT_THROTTLE_CLASSES`/`_RATES` at all —
same unbounded-free-usage exposure as dotnet's identical finding.

**Fix:** DRF's `ScopedRateThrottle`, set globally in `REST_FRAMEWORK`, with
per-view opt-in via a `throttle_scope` attribute (views without one are
unaffected):
```python
"DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
"DEFAULT_THROTTLE_RATES": {"identify": "10/min", "bite-score": "30/min"},
```
`IdentifyView.throttle_scope = "identify"`,
`BiteScoreTodayView`/`BiteScoreForecastView.throttle_scope = "bite-score"` —
same rates as omyfish-dotnet. Regs endpoints are left unthrottled, matching
dotnet's own scope (it didn't rate-limit its regs proxies either).

### 1.3 Refresh token in response body + `localStorage`

**Problem:** `apps/accounts/serializers.py::auth_response` returned
`refreshToken` in the JSON body; the shared frontend
(`AuthContext.tsx`) stored it in `localStorage` — same XSS token-theft
exposure as dotnet's identical finding.

**Fix — httpOnly cookie**, same shape as dotnet's:
```python
REFRESH_COOKIE_NAME = "refresh_token"

def _set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        REFRESH_COOKIE_NAME, str(refresh_token),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True, secure=not settings.DEBUG, samesite="Strict",
        path="/api/v1/auth",
    )
```
`RefreshView` now reads `request.COOKIES.get(REFRESH_COOKIE_NAME)` instead
of the body; added `POST /api/v1/auth/logout` to clear it. `auth_response`
no longer includes `refreshToken`. Frontend (`AuthContext.tsx`, `api.ts`)
updated to match dotnet's already-shipped version: `credentials: "include"`
on every auth call, no more `omyfish_refresh` in `localStorage`.

**Required companion change**: `CORS_ALLOW_CREDENTIALS = True`. Without it,
`django-cors-headers` doesn't set `Access-Control-Allow-Credentials`, and
the browser rejects the cross-origin `credentials: "include"` fetch
entirely (not just the cookie — the whole response becomes unreadable by
JS). Confirmed safe to combine with `CORS_ALLOW_ALL_ORIGINS = True`:
`corsheaders/middleware.py` reflects the exact request `Origin` (never a
literal `"*"`) whenever credentials are allowed.

Verified live: register/login set the cookie (`HttpOnly`, `SameSite=Strict`,
`Path=/api/v1/auth`); refresh works from the cookie and 401s without one;
logout clears it (`Max-Age=0`). New tests in `apps/accounts/tests.py`
(`AuthFlowTests`) cover the same.

### 1.4 Containers run as root

**Problem:** the root `Dockerfile` (Django backend) had no `USER`
directive — confirmed root by `docker run --rm --entrypoint id`.
`frontend/omyfish-web/Dockerfile` already did the right thing (it's shared
with the siblings, already fixed via item C's baseline sync).

**Fix:**
```dockerfile
RUN addgroup --system --gid 1001 django && adduser --system --uid 1001 --gid 1001 django
USER django
```
No Kubernetes manifests or Helm chart exist in this repo (docker-compose
only per `ARCHITECTURE.md`), so the K8s `securityContext` half of dotnet's
finding doesn't apply here. Verified: `docker run --rm --entrypoint id
omyfish-python-web-django` → `uid=1001(django)`.

---

## 2. Resilience

**Status: §2.2 fixed 2026-09-11. §2.1 partially already fine (timeouts
exist), retry/circuit-breaker not done. §2.3/§2.4 confirmed not applicable.**

### 2.1 No timeout/retry/circuit breaker on the AI service client

**Already fine (timeouts) / not done (retry, circuit breaker).**
`apps/species/ai_client.py` sets `timeout=30` on every `requests` call — the
specific "hangs forever" failure mode dotnet fixed doesn't exist here. No
retry policy or circuit breaker exists though (no `tenacity`, no
`HTTPAdapter`-mounted `Retry`), so a transient blip still surfaces
immediately as a 503. **Not fixed in this pass** — smaller/lower-urgency
than the security tier; left for a follow-up (see BACKLOG.md item G).

### 2.2 No centralized exception handling

**Problem:** no custom DRF `EXCEPTION_HANDLER` — a genuinely unhandled
exception fell through to Django's own error response, which is the
DEBUG-mode HTML debug page whenever a deploy forgets to set `DEBUG=False`
(and `DEBUG` defaults to `True` here — see Bonus findings).

**Fix:** `config/exception_handler.py` wraps DRF's default handler; if that
returns `None` (a truly unhandled exception), logs it and returns a
structured `{"error": "..."}` 500 instead. Registered via
`REST_FRAMEWORK["EXCEPTION_HANDLER"]`.

### 2.3 Dual-write without an outbox

**Not applicable — confirmed structurally.** No message broker exists
anywhere in this repo (no celery/kombu/pika/kafka in `requirements.txt` or
imports), no Django signals, no `transaction.atomic` usage — nothing does
two related writes that need to be coupled. This category is specific to
services that publish integration events across a process boundary.

### 2.4 No consumer idempotency

**Not applicable — confirmed, no consumers exist.** Same evidence as §2.3.
Bonus: the `Notification` model has no producer anywhere in application
code (see Bonus findings) — the read-side API exists with no write-side
trigger, so it always returns an empty list today, independent of this
audit.

---

## 3. Data layer

**Status: all already fine — no fixes needed.**

### 3.1 / 3.2 ORM auto-schema / incomplete migration runner

**Already fine.** Django's migration framework has no
`EnsureCreatedAsync()`-equivalent auto-schema call, and both the local
(`make run`) and container (`Dockerfile` `CMD`) paths explicitly run
`migrate --noinput` before serving traffic. `make migrate` runs bare
`python manage.py migrate` with no hand-maintained file list to drift out
of sync (Django auto-discovers every installed app's migrations) — verified
`makemigrations --check --dry-run` reports no drift across all 5 apps.

### 3.3 Dead PostGIS geometry column

**Not applicable — deliberate, documented tradeoff, no dead infra exists.**
`apps/observations/models.py` uses plain `latitude`/`longitude` floats with
an explicit "pragmatic scaffold" comment; `ARCHITECTURE.md`'s "Geo:
pragmatic scaffold vs. PostGIS upgrade" section spells out the not-yet-done
upgrade path. There's no half-built geometry column/index/function sitting
unused — infrastructure was never built, rather than built-then-abandoned
like dotnet's version of this finding.

### 3.4 N+1 query

**Already fine.** No per-item DB lookups inside a loop found in the
identify flow or any list endpoint; `apps/observations/views.py` and
`apps/billing/admin_views.py` (`.select_related("user")`) already query
correctly.

---

## 4. Testing/CI

**Status: partially fixed 2026-09-11** (auth-flow + permission-default
tests added; full CI pipeline and broader test coverage still open).

**Problem:** all five `apps/*/tests.py` were unmodified Django boilerplate
stubs — zero real tests anywhere, including zero coverage of the exact kind
of bug this audit's security tier fixed (a `permission_classes`/cookie
regression that only a real request/response cycle, not a unit test of
view logic in isolation, would catch). No `.github/workflows/` directory
exists — no CI of any kind, not even a bare test run.

**Fixed:** `apps/accounts/tests.py` now has `AuthFlowTests` (register/login/
refresh/logout cookie behavior) and `PermissionDefaultTests` (unauthenticated
access to observations/notifications/billing returns 401; species catalog
stays public) — 9 tests, all passing.

**Still open:** no tests for `apps/species`, `apps/observations`,
`apps/notifications`, `apps/billing`; no CI workflow of any kind (`dotnet`
siblings have `.github/workflows/ci.yml` running at least `dotnet test`,
this repo has nothing). Left for a follow-up pass — see BACKLOG.md item G.

---

## Cleanup

**Status: confirmed minor, nothing fixed.** No Helm chart/K8s manifests
exist to have incomplete placeholders (docker-compose only deploy path).
One harmless untracked WSL artifact (`.env:Zone.Identifier`) — not a code
issue, not touched.

---

## Bonus findings (not on the dotnet list, found during this pass)

1. **Notification feature has no producer anywhere.** `apps/notifications`
   exposes list/mark-read, but nothing in application code ever calls
   `Notification.objects.create(...)` — the endpoint always returns an
   empty list today. Not fixed in this pass (feature gap, not a security/
   resilience defect); flagged for whoever picks up the notification
   feature next.
2. **`DEBUG` defaults to `True`**, and `SECRET_KEY`/`AWS_SECRET_ACCESS_KEY`/
   `JWT_SECRET` all ship with hardcoded dev-fallback defaults that don't
   fail closed if the corresponding env var is forgotten in production.
   Not fixed in this pass — worth its own follow-up given it compounds any
   future bug (leaks stack traces on top of running with insecure secrets).
3. **CORS is wide open** (`CORS_ALLOW_ALL_ORIGINS = True`, intentionally
   mirroring the Java/.NET gateways' dev config) — now combined with
   `CORS_ALLOW_CREDENTIALS = True` for the refresh cookie to work. Safe per
   django-cors-headers' origin-reflection behavior (see §1.3), but worth
   revisiting alongside a real production CORS allowlist if this repo ever
   deploys somewhere the frontend isn't same-site with the backend.
