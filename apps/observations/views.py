from django.shortcuts import get_object_or_404
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Observation
from .serializers import ObservationSerializer


class ObservationListCreateView(ListCreateAPIView):
    serializer_class = ObservationSerializer

    def get_queryset(self):
        return Observation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ObservationDeleteView(APIView):
    def delete(self, request, observation_id):
        observation = get_object_or_404(
            Observation, id=observation_id, user=request.user
        )
        observation.delete()
        return Response(status=204)


class ObservationGeoJSONView(APIView):
    def get(self, request):
        observations = Observation.objects.filter(user=request.user)
        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [obs.longitude, obs.latitude],
                },
                "properties": {
                    "id": str(obs.id),
                    "speciesName": obs.species_name,
                    "scientificName": obs.scientific_name,
                    "confidence": obs.confidence,
                    "notes": obs.notes,
                    "observedAt": obs.observed_at.isoformat(),
                },
            }
            for obs in observations
        ]
        return Response({"type": "FeatureCollection", "features": features})
