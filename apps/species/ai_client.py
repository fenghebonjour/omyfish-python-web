import base64
import uuid

import requests
from django.conf import settings


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
    response = requests.post(
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
        "imageKey": str(uuid.uuid4()),
    }


def bite_score(path, lat, lon, species="general", hours=None):
    params = {"lat": lat, "lon": lon, "species": species}
    if hours is not None:
        params["hours"] = hours
    response = requests.get(
        f"{settings.AI_SERVICE_URL}/bite-score/{path}", params=params, timeout=30
    )
    response.raise_for_status()
    return camelize(response.json())
