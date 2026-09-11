import base64

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Retries transient failures (connection errors, 502/503/504) against the external AI service
# instead of surfacing a 503 to the user on the first blip — timeouts alone (already set on
# every call below) don't help when the failure is a dropped connection or a brief upstream
# restart (BACKLOG.md item G, WEAKNESS_AUDIT.md §2.1). No circuit breaker added, matching the
# dotnet/java siblings' own decision to ship the timeout/retry first.
_session = requests.Session()
_retry = Retry(total=2, backoff_factor=0.2, status_forcelist=[502, 503, 504])
_session.mount("http://", HTTPAdapter(max_retries=_retry))
_session.mount("https://", HTTPAdapter(max_retries=_retry))


def camelize_key(key):
    parts = key.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def camelize(obj):
    if isinstance(obj, dict):
        return {camelize_key(k): camelize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [camelize(item) for item in obj]
    return obj


def identify(image_bytes, top_k=5):
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    response = _session.post(
        f"{settings.AI_SERVICE_URL}/predict",
        json={"image_base64": image_base64, "top_k": top_k},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "predictions": camelize(data["predictions"]),
        "uncertain": data["uncertain"],
        "isFish": data["is_fish"],
    }


def bite_score(path, lat, lon, species="general", hours=None):
    params = {"lat": lat, "lon": lon, "species": species}
    if hours is not None:
        params["hours"] = hours
    response = _session.get(
        f"{settings.AI_SERVICE_URL}/bite-score/{path}", params=params, timeout=30
    )
    response.raise_for_status()
    return camelize(response.json())


# Quebec Regs Advisor — thin proxy to omyfish-ai's /regs/* endpoints (chatbot/
# retrieval logic stays there, frozen). Same pattern as bite_score() above.

def regs_limits(lat, lon, species="general"):
    response = _session.get(
        f"{settings.AI_SERVICE_URL}/regs/limits",
        params={"lat": lat, "lon": lon, "species": species},
        timeout=30,
    )
    response.raise_for_status()
    return camelize(response.json())


def regs_zones_geojson():
    response = _session.get(f"{settings.AI_SERVICE_URL}/regs/zones/geojson", timeout=30)
    response.raise_for_status()
    return response.json()  # raw GeoJSON — passed through untouched, not camelized


def regs_consumption_stations(lat, lon, limit=5):
    response = _session.get(
        f"{settings.AI_SERVICE_URL}/regs/consumption/stations",
        params={"lat": lat, "lon": lon, "limit": limit},
        timeout=30,
    )
    response.raise_for_status()
    return camelize(response.json())


def regs_consumption(lat, lon, species="general", size_cm=None):
    params = {"lat": lat, "lon": lon, "species": species}
    if size_cm is not None:
        params["size_cm"] = size_cm
    response = _session.get(
        f"{settings.AI_SERVICE_URL}/regs/consumption", params=params, timeout=30
    )
    response.raise_for_status()
    return camelize(response.json())


def regs_ask(question):
    response = _session.post(
        f"{settings.AI_SERVICE_URL}/regs/ask", json={"question": question}, timeout=30
    )
    response.raise_for_status()
    return camelize(response.json())
