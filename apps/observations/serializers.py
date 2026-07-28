from rest_framework import serializers

from .models import Observation


class ObservationSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    speciesName = serializers.CharField(source="species_name")
    scientificName = serializers.CharField(source="scientific_name", required=False, allow_null=True)
    imageUrl = serializers.URLField(source="image_url", required=False, allow_null=True)
    observedAt = serializers.DateTimeField(source="observed_at", read_only=True)

    class Meta:
        model = Observation
        fields = [
            "id",
            "speciesName",
            "scientificName",
            "confidence",
            "notes",
            "latitude",
            "longitude",
            "imageUrl",
            "source",
            "observedAt",
        ]
