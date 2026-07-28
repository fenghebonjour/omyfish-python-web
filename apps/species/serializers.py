from rest_framework import serializers

from .models import Species


class SpeciesSerializer(serializers.ModelSerializer):
    commonName = serializers.CharField(source="common_name")
    scientificName = serializers.CharField(source="scientific_name")
    maxSizeCm = serializers.FloatField(source="max_size_cm")
    conservationStatus = serializers.CharField(source="conservation_status")
    funFact = serializers.CharField(source="fun_fact")
    northAmericanFreshwater = serializers.BooleanField(source="north_american_freshwater")

    class Meta:
        model = Species
        fields = [
            "key",
            "commonName",
            "scientificName",
            "habitat",
            "diet",
            "maxSizeCm",
            "conservationStatus",
            "description",
            "funFact",
            "northAmericanFreshwater",
        ]
