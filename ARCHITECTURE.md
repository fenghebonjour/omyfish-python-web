# OMyFish Python-Web (Django) Architecture

## Why a monolith, not a microservice mirror

The Java and .NET siblings each split into 4-5 microservices behind an API
gateway because that's idiomatic for their ecosystems. Django's idiomatic
shape is different: **one project, several apps, one process** — splitting
`accounts`/`species`/`observations` into separate deployables would fight the
framework for no benefit at this scale. So this repo is a single Django
monolith whose DRF layer reproduces the *same* REST contract the frontend
already speaks to the Java/.NET gateways. Django itself plays the role the
`api-gateway` service plays for the others — one origin, no separate
gateway/message-broker tier required.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                        │
│                    Browser (Next.js SPA, shared verbatim)                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ HTTPS — single origin (localhost:8080)
┌────────────────────────────────▼────────────────────────────────────────────┐
│                    DJANGO MONOLITH (config/ + apps/)                        │
│   accounts · species · observations · notifications · billing               │
│   DRF + SimpleJWT — plays the api-gateway role, no separate gateway needed   │
└──────────────────────────────────┬───────────────────────────────────────── ┘
                                   │ HTTP
                                   ▼
                          ┌─────────────────┐
                          │   AI Service    │
                          │  (omyfish-ai)    │
                          │  FastAPI/PyTorch │
                          └─────────────────┘
┌────────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + PostGIS (single `omyfish` DB)               │
│              or SQLite for local `make run` — see Geo section below         │
└────────────────────────────────────────────────────────────────────────────┘
```

## App Decomposition

| App             | Responsibility                                                  |
|-----------------|-------------------------------------------------------------------|
| `accounts`      | Custom `User` (email as username, `role`), JWT register/login/refresh |
| `species`       | Species catalog, `/identify` and `/bite-score` proxies to `omyfish-ai` |
| `observations`  | Observation CRUD, GeoJSON export                                  |
| `notifications` | Per-user notifications, mark-as-read                              |
| `billing`       | Subscription self-service (`/billing/me`, `/billing/checkout`) + admin ops |

## REST Contract

All JSON is camelCase; ids are string UUIDs. JWT auth responses share one
shape: `{token, refreshToken, userId, email, role}`.

- `POST /api/v1/auth/register` · `POST /api/v1/auth/login` · `POST /api/v1/auth/refresh`
- `POST /api/v1/species/identify` (multipart `image`, `topK`) → `{predictions[], uncertain, imageKey, isFish}`
  — `imageKey` is a real object-storage key (identify persists the image), not a placeholder.
- `GET /api/v1/species/bite-score/today|forecast?lat&lon&species[&hours]`
- `GET /api/v1/species?northAmericanFreshwater=`
- `GET/POST /api/v1/observations` (create body references `imageStorageKey` from a
  prior `/identify` call rather than re-uploading the image), `DELETE /api/v1/observations/{id}`,
  `GET /api/v1/observations/geojson`
- `GET /api/v1/notifications`, `PUT /api/v1/notifications/{id}/read`
- `GET /api/v1/billing/me`, `POST /api/v1/billing/checkout`
- `GET /api/v1/admin/stats`, `GET /api/v1/admin/subscriptions`, `POST /api/v1/admin/subscriptions/{id}/{grant|revoke|extend-trial}`

## AI Service Integration

`apps/species/ai_client.py` calls `omyfish-ai` over HTTP exactly like the
Java/.NET adapters do:

- `identify()` → AI `POST /predict` `{image_base64, top_k}`; maps
  `common_name` → `commonName` (and the rest of the response) to camelCase.
  `apps/species/views.py::IdentifyView` then persists the uploaded image via
  Django's default storage and attaches the real key as `imageKey` (the AI
  service itself doesn't return one — see "Object Storage" below).
- `bite_score()` → AI `GET /bite-score/{today,forecast}`; response is the
  same six-factor-breakdown shape as the siblings — recursively camelCased,
  never reduced to just the headline score.

## Object Storage

`/identify` persists the uploaded image and returns a real storage key as
`imageKey`; `POST /api/v1/observations` then references that key via
`imageStorageKey` instead of re-uploading — the same two-step contract as the
Java/.NET siblings. Storage backend follows the same dev-vs-docker split as
the database: local disk (`MEDIA_ROOT`) when `MINIO_ENDPOINT_URL` is unset (so
`make run` needs no external services), MinIO (via `django-storages`'
S3-compatible backend) when it is — see `config/settings.py`'s `STORAGES`
block and `docker-compose.yml`'s `minio` service.

## Geo: pragmatic scaffold vs. PostGIS upgrade

`Observation.latitude`/`longitude` are plain floats, and
`ObservationGeoJSONView` builds the `FeatureCollection` in Python. This means
`make run` works instantly on SQLite — no GDAL/GEOS install required for
local dev. `docker-compose.yml` still ships a `postgis/postgis` image (like
the siblings) so the upgrade path is a small diff, not a rewrite:

1. Add `django.contrib.gis` to `INSTALLED_APPS`, switch the DB engine to
   `django.contrib.gis.db.backends.postgis`.
2. Replace `latitude`/`longitude` floats with a single
   `location = gis_models.PointField(geography=True)`.
3. Add a spatial index (`GistIndex`) on `location`; rebuild the GeoJSON view
   with `django.contrib.gis.serializers.geojson` or `.annotate(geojson=...)`.
4. Update `ObservationSerializer`/`ai_client` call sites that read
   `latitude`/`longitude` directly to use `location.y`/`location.x`.

Nothing else in the request/response contract changes — the frontend already
consumes plain GeoJSON.

## Frontend

`frontend/omyfish-web/` is the Next.js 15 SPA copied verbatim from
`omyfish-java`. It talks to whichever backend is at `NEXT_PUBLIC_API_URL`
(default `http://localhost:8080`) — zero component changes needed to point it
at this Django backend instead of a Java/.NET gateway.
