from django.core.files.storage import default_storage
from rest_framework import serializers

from .models import Observation


class ObservationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    speciesName = serializers.CharField(source="species_name")
    scientificName = serializers.CharField(source="scientific_name", required=False, allow_null=True)
    topConfidence = serializers.FloatField(source="top_confidence", required=False, allow_null=True)
    imageStorageKey = serializers.CharField(source="image_storage_key")
    imageUrl = serializers.SerializerMethodField()
    observedAt = serializers.DateTimeField(source="observed_at", read_only=True)

    class Meta:
        model = Observation
        fields = [
            "id",
            "speciesName",
            "scientificName",
            "topConfidence",
            "notes",
            "latitude",
            "longitude",
            "imageStorageKey",
            "imageUrl",
            "source",
            "observedAt",
        ]

    def get_imageUrl(self, obj):
        if not obj.image_storage_key:
            return None
        return default_storage.url(obj.image_storage_key)
