import uuid

from django.conf import settings
from django.db import models


class Observation(models.Model):
    # Pragmatic scaffold: plain lat/lon floats so `make run` works instantly on
    # SQLite with no GDAL/GEOS. See ARCHITECTURE.md for the GeoDjango
    # PointField + PostGIS spatial-index upgrade path.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="observations"
    )
    species_name = models.CharField(max_length=255)
    scientific_name = models.CharField(max_length=255, blank=True, null=True)
    top_confidence = models.FloatField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    # References the key /identify already stored the image under — the
    # image is already uploaded by then, so observation-create just points
    # at it instead of re-uploading (family-wide two-step contract).
    image_storage_key = models.CharField(max_length=500, blank=True, null=True)
    source = models.CharField(max_length=50, default="manual")
    observed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at"]

    def __str__(self):
        return f"{self.species_name} @ ({self.latitude}, {self.longitude})"
