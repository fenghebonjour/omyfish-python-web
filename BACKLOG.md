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

---

## [x] H — Payment module parity, phase 1: a real Stripe integration

**Status:** DONE (2026-10-10). Port of `omyfish-java`'s item H — except
there was nothing to upgrade here, only to build: `apps/billing`'s
`Subscription` had no `stripe_customer_id`/`stripe_subscription_id` at
all, and `CheckoutView.post` was a literal 503 stub.

1. ~~`Subscription` model~~ — **DONE.** Added `stripe_customer_id`
   (indexed — it's the webhook lookup key), `stripe_subscription_id`,
   `payment_processor`, `last_payment_reference` (phase I's Adyen need,
   added here since it's the same migration pass) —
   `0002_processedwebhookevent_and_more.py`, generated via
   `manage.py makemigrations` rather than hand-written SQL (the Django
   idiom; the Go/dotnet siblings hand-write migrations because their ORMs
   don't autogenerate them).
2. ~~Real checkout~~ — **DONE.** `apps/billing/gateways/stripe_gateway.py`
   (`StripeGateway.create_subscription_intent`):
   `stripe.Subscription.create(payment_behavior="default_incomplete",
   expand=["latest_invoice.confirmation_secret"], idempotency_key=...)`,
   returning `{processor, clientSecret, subscriptionId, status}` — the
   exact shape `omyfish-frontend`'s `CheckoutResponse` type expects,
   confirmed by reading it, not assumed. The installed `stripe` package's
   actual TypedDict params and resource fields (confirmed via
   `inspect.getsource` on the installed package, not guessed from the
   Java/dotnet siblings' shape) turned out to match the Java/dotnet
   siblings closely: `RequestOptions` (incl. `idempotency_key`) is mixed
   directly into each call's own params dict rather than a separate
   options object, and `invoice.parent.subscription_details.subscription`/
   `invoice.confirmation_secret.client_secret` are the same nested paths
   dotnet's Stripe.net needed reflection to confirm.
3. ~~Webhook endpoint~~ — **DONE.** `POST /api/v1/billing/webhook/<processor>`
   (`WebhookView`, `AllowAny` — no gateway-level auth-filter gap to find
   here, since this is a monolith with no separate API gateway service
   unlike the Java/dotnet siblings), dispatching to whichever gateway the
   `processor` path segment names via a plain dict-based registry (see
   item I.4). `customer.subscription.updated`/`.deleted` → apply
   status/plan/period-end to the local row via the same effects path
   admin/reconciliation also use.
4. ~~Admin refund~~ — **DONE.** `RefundView` alongside
   `GrantView`/`RevokeView`/`ExtendTrialView`, resolving the
   subscription's latest paid invoice to a PaymentIntent
   (`stripe.InvoicePayment.list(invoice=..., status="paid")`) and
   refunding that; local subscription status untouched (refund and
   cancel are separate decisions, same as the Java/dotnet siblings).
5. ~~Saved payment method / SetupIntent~~ — **DONE.**
   `POST /api/v1/billing/payment-method/setup` (`stripe.SetupIntent`,
   `usage="off_session"`) + a `setup_intent.succeeded` webhook case
   mapped to `payment_method_attached`, applied via
   `services._apply_event_effects` calling the gateway's
   `set_default_payment_method`.

Verified: `python manage.py test apps` — 48/48 green (9 pre-existing +
39 new `apps/billing/tests.py` cases, service- and view-level). A
`FakeGateway` test double stands in for the real Stripe/PayPal/Adyen
gateways throughout, the same role NSubstitute/Mockito mocks play in the
Java/dotnet test suites, since this environment has no real processor
test credentials.

---

## [x] I — Payment module parity, phase 2: idempotency, dedup, reconciliation, multi-processor

**Status:** DONE (2026-10-10). Port of `omyfish-java`'s item I, including
its later multi-processor and idempotency-key-reuse-after-crash
additions.

1. ~~Idempotency keys on checkout/refund~~ — **DONE.** `IdempotencyRecord`
   model (`(key, endpoint)` `UniqueConstraint`, same shape as the
   Java/dotnet siblings' `IdempotencyRecord`) +
   `services._reserve`/`_is_orphaned`/`_require_owner`. A race on the
   same key is caught via Django's own `IntegrityError` wrapping the
   unique-constraint violation — no SQL-state-code special-casing needed
   the way dotnet's Postgres-specific `23505` check or a hand-rolled SQL
   migration would, since Django's ORM abstracts that away identically
   across SQLite (used by `manage.py test`) and Postgres (used in
   Docker) — same destination as the Java/dotnet siblings, a simpler
   vehicle to get there. `services.start_checkout`/`refund` both reserve
   → call the gateway → complete-or-delete, with the replay path for a
   repeated key and the orphaned-reservation retry (`_is_orphaned`,
   1-minute threshold, same as Java/dotnet). The same key is also passed
   to `stripe-python`'s own `idempotency_key=` kwarg on every call — the
   second, independent layer the Java/dotnet siblings' design relies on.
2. ~~Webhook event dedup~~ — **DONE.** `ProcessedWebhookEvent` model
   keyed by the provider's event id. `services.apply_event` checks it
   before delegating to `_apply_event_effects`, recording the id after a
   handled event — exact split the Java/dotnet siblings use between
   `applyEvent`/`applyEventEffects` (`ApplyEventAsync`/
   `ApplyEventEffectsAsync` in dotnet).
3. ~~Reconciliation job~~ — **DONE**, and built the way the backlog
   itself flagged it should be: `services.reconcile(since)` plus
   `manage.py reconcile_subscriptions --lookback-hours=24` (a Django
   management command — the natural fit here, unlike Java's Spring
   `@Scheduled` or dotnet's admin-endpoint-only trigger — meant to run
   from cron/Celery beat/a Kubernetes CronJob), *and*
   `POST /api/v1/admin/subscriptions/reconcile?lookbackHours=24` for an
   on-demand admin trigger matching the siblings' own endpoint. Ported
   1:1 from Java's `relink`/`resyncStatus` split: relink repairs a
   missing/mismatched local link (creating a trial row first via
   `get_or_create(..., defaults={"trial_end": timezone.now()})` — a
   "trial of 0 days," immediately expired, if the user has none at all,
   matching Java's `Subscription.startTrial(userId, 0)` rather than
   looking like a fresh active trial), resync replays through
   `apply_event` with no `event_id` set so the webhook-dedup check from
   item I.2 doesn't interfere.
4. ~~Multi-processor: PayPal + Adyen~~ — **DONE.**
   `apps/billing/gateways/` (`base.py`'s `PaymentGateway` —
   a `typing.Protocol`, Python's nearest equivalent to Java's
   `PaymentPort` interface/dotnet's `IPaymentGateway` — plus dataclasses
   for `SubscriptionIntent`/`SetupIntentResult`/`RefundResult`/
   `PaymentEvent`/`ReconciliationCandidate`; `registry.py`'s
   `default_gateway()`/`exists()`/`by_name()`/`configured()`, ported 1:1
   from the Java/dotnet siblings' `PaymentProcessorRegistry`).
   `StripeGateway` (above). `PayPalGateway`: hand-rolled REST via
   `requests`, same reasoning as the Java/dotnet siblings' own adapters
   — PayPal has no first-party Python SDK worth depending on either.
   `AdyenGateway`: the official `Adyen` PyPI package (16.0.0, confirmed
   actively maintained — regular releases, owned by Adyen — before
   depending on it, same discipline as the Java/dotnet siblings). Its
   actual API (confirmed via `inspect.getsource` on the installed
   package rather than guessed) turned out to be the *simpler*,
   classic-style shape Java's adapter uses
   (`client.checkout.payments_api.sessions(request_dict,
   idempotency_key=...)`, plain dicts in/out, `Adyen.util
   .is_valid_hmac_notification`) rather than dotnet's 36.1.0
   DI/`IHostBuilder`-registered-services shape — the two .NET and Python
   SDKs for the same provider turned out to have diverged architecturally
   from each other, not just from Java's older version, worth noting for
   whoever next touches either. Request field casing/enum values
   (`recurringProcessingModel: "Subscription"`, `storePaymentMethodMode:
   "enabled"`) were confirmed by reflecting on the actual string values
   dotnet's typed SDK serializes its own enum members to, rather than
   guessed from casing convention, since Adyen's API mixes PascalCase and
   camelCase enum values inconsistently across fields.
   `Subscription.payment_processor` (above, phase H's migration).
   `PaymentEvent.processor` defaults to `"stripe"` (every event
   constructed before multi-processor support existed was implicitly
   Stripe's). The webhook endpoint already took a `<str:processor>` path
   segment from the start (phase H), so no later route change was needed
   here the way the dotnet port needed one.

Verified: `python manage.py test apps` — 48/48 green, included in phase
H's total above (built together in this environment rather than as
separate passes, since there's no existing code to port item-by-item
against — see phase H's "Verified" note for the breakdown).

---

## [x] J — Payment module parity, phase 3: Customer Portal, plan propagation, past_due

**Status:** DONE (2026-10-10). Port of the *payment-specific* parts of
`omyfish-java`'s item J — not change-password/nav-wiring, which are
account features the shared frontend already handles identically across
all three backends regardless of which one is running.

1. ~~Stripe Customer Portal~~ — **DONE.**
   `POST /api/v1/billing/portal-session` (`PortalSessionSerializer
   {returnUrl}` → `{url}`, the exact shape confirmed against
   `omyfish-frontend`'s `api.billing.portalSession`, not assumed) →
   `services.create_portal_session` → `StripeGateway
   .create_portal_session` (`stripe.billing_portal.Session.create`);
   `PayPalGateway`/`AdyenGateway` both return `None` (no portal
   equivalent for either, same decision the Java/dotnet siblings made).
   Same 404-vs-503 split as `refund`: no subscription
   (`Subscription.DoesNotExist`) or no customer id on file
   (`NoProcessorCustomerError`) → 404; no portal for this processor
   (`None`) → 503, which the shared frontend's "contact support"
   fallback already handles gracefully.
2. ~~Webhook plan propagation~~ — **DONE, checked deliberately per this
   item's own warning, not assumed fine.** Since this was a ground-up
   build rather than a port, there was no existing Stripe-adapter bug to
   rediscover the way the dotnet port found one in its own
   pre-existing code — but the same wrong assumption was still a trap
   worth avoiding on a *fourth* implementation (Java's Stripe/PayPal,
   dotnet's Stripe, now this one): `StripeGateway._from_subscription_event`
   reads `item.price.id` off the subscription's first item and reverses
   it through `_plan_for_price_id` (mirroring `PayPalGateway
   ._plan_for_plan_id`, built the same way in phase I.4) rather than
   leaving `plan` unset. `services._apply_event_effects`'s
   `subscription_updated` case reads `event.plan or subscription.plan or
   "monthly"` — written correctly the first time here specifically
   because this item's own text named the exact bug to watch for before
   any webhook-handling code was written, not caught in review after.
3. ~~Past_due status~~ — **DONE.** `Subscription.PAST_DUE` +
   `mark_past_due()`; driven by a new `invoice.payment_failed` Stripe
   webhook case (`StripeGateway._from_invoice_payment_failed`, reading
   the subscription id off `invoice.parent.subscription_details
   .subscription` — confirmed via `inspect.getsource` on the installed
   `stripe` package rather than assumed, the same discipline dotnet's
   port needed reflection against the Stripe.net DLL for) mapped to a
   new `payment_failed` `services._apply_event_effects` case.

Verified: included in phase H's `python manage.py test apps` total (48/48
green) — built together with phases H/I rather than as a separate pass,
since there was no existing code to port item-by-item against. Test
coverage specific to this item: plan-overwritten-on-event /
plan-kept-when-event-has-none (the propagation check), payment_failed →
past_due, portal-session delegate + no-customer-id-404.

---

## [x] K — Payment module parity, phase 4: guard against a duplicate subscription

**Status:** DONE (2026-10-10). Port of `omyfish-java`'s item K — found
live there, not in testing: a second checkout call with a different
idempotency key created a second, separate, active Stripe subscription
for a user who already had one, both billing monthly. Confirmed there
with real Stripe data (`stripe invoices list --customer <id>`), not
assumed.

The actual lesson, carried over deliberately rather than reinvented:
idempotency keys (phase I) only guarantee "this exact request happens
once," never "this user doesn't already have what they're asking to
create" — a business invariant needs its own explicit check.
`services.start_checkout` now checks this right after the same-key
replay path (so a genuine retry of an in-flight/completed checkout is
unaffected) and before reserving a new idempotency key or touching the
gateway at all: if the user's subscription row already has
`stripe_subscription_id` set and `effective_status` is `active` or
`past_due`, it raises a new `AlreadySubscribedError`, mapped to `409
Conflict` at `CheckoutView` — a distinct exception from
`Subscription.DoesNotExist`/`NoProcessorCustomerError` (→404, "no such
thing") and `IdempotencyConflictError` (→409, "this key is still in
flight") so the three failure modes stay distinguishable in the view's
except chain the way Java/dotnet's separate `catch` blocks are. A
`trialing` user with no processor attached yet is unaffected (explicit
test coverage, not just inferred from the condition).

Also carried forward deliberately, not fixed, matching the Java/dotnet
siblings' own decision: webhook-to-local-row matching is still keyed on
the processor customer id alone (`Subscription.objects.filter
(stripe_customer_id=event.customer_id)`), not which specific subscription
an event is about — safe only because this phase's guard makes a
customer having two live subscriptions at once much rarer, not because
that matching was actually fixed. Left as-is here too, for the same
reason dotnet gave: diverging behavior between ports for a case none of
the three has actually hit isn't worth it.

Verified: included in phase H's `python manage.py test apps` total
(48/48 green) — built together with phases H/I/J rather than as a
separate pass. Test coverage specific to this item:
already-active-subscriber and already-past-due-subscriber guards both
fire without calling the gateway, trialing-with-no-processor is
unaffected. All four payment-module-parity items (H, I, J, K) are now
done.
