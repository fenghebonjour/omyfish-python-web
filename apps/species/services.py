import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from . import ai_client


def identify(image_bytes, image_name, top_k=5):
    result = ai_client.identify(image_bytes, top_k=top_k)
    storage_key = default_storage.save(
        f"identify/{uuid.uuid4()}/{image_name}", ContentFile(image_bytes)
    )
    result["imageKey"] = storage_key
    return result
