import uuid

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import ai_client
from .models import Species
from .serializers import SpeciesSerializer


class SpeciesListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = SpeciesSerializer

    def get_queryset(self):
        queryset = Species.objects.all()
        flag = self.request.query_params.get("northAmericanFreshwater")
        if flag is not None:
            queryset = queryset.filter(north_american_freshwater=flag.lower() == "true")
        return queryset


class IdentifyView(APIView):
    def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response({"detail": "image is required"}, status=status.HTTP_400_BAD_REQUEST)
        top_k = int(request.data.get("topK", 5))
        image_bytes = image.read()
        try:
            result = ai_client.identify(image_bytes, top_k=top_k)
        except requests.RequestException:
            return Response(
                {"detail": "AI service unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        storage_key = default_storage.save(
            f"identify/{uuid.uuid4()}/{image.name}", ContentFile(image_bytes)
        )
        result["imageKey"] = storage_key
        return Response(result)


class BiteScoreTodayView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return _bite_score_response(request, "today")


class BiteScoreForecastView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return _bite_score_response(request, "forecast")


def _bite_score_response(request, path):
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    if lat is None or lon is None:
        return Response({"detail": "lat and lon are required"}, status=status.HTTP_400_BAD_REQUEST)
    species = request.query_params.get("species", "general")
    hours = request.query_params.get("hours")
    try:
        result = ai_client.bite_score(
            path, lat=lat, lon=lon, species=species, hours=hours
        )
    except requests.RequestException:
        return Response(
            {"detail": "AI service unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return Response(result)


# Quebec Regs Advisor — thin proxy to omyfish-ai (frozen), mirrors the
# bite-score proxy pattern above.

class RegsLimitsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lat = request.query_params.get("lat")
        lon = request.query_params.get("lon")
        if lat is None or lon is None:
            return Response({"detail": "lat and lon are required"}, status=status.HTTP_400_BAD_REQUEST)
        species = request.query_params.get("species", "general")
        try:
            return Response(ai_client.regs_limits(lat, lon, species))
        except requests.RequestException:
            return _regs_unavailable()


class RegsZonesGeoJsonView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            return Response(ai_client.regs_zones_geojson())
        except requests.RequestException:
            return _regs_unavailable()


class RegsConsumptionStationsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lat = request.query_params.get("lat")
        lon = request.query_params.get("lon")
        if lat is None or lon is None:
            return Response({"detail": "lat and lon are required"}, status=status.HTTP_400_BAD_REQUEST)
        limit = request.query_params.get("limit", 5)
        try:
            return Response(ai_client.regs_consumption_stations(lat, lon, limit))
        except requests.RequestException:
            return _regs_unavailable()


class RegsConsumptionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lat = request.query_params.get("lat")
        lon = request.query_params.get("lon")
        if lat is None or lon is None:
            return Response({"detail": "lat and lon are required"}, status=status.HTTP_400_BAD_REQUEST)
        species = request.query_params.get("species", "general")
        size_cm = request.query_params.get("sizeCm")
        try:
            return Response(ai_client.regs_consumption(lat, lon, species, size_cm))
        except requests.RequestException:
            return _regs_unavailable()


class RegsAskView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        question = request.data.get("question")
        if not question:
            return Response({"detail": "question is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(ai_client.regs_ask(question))
        except requests.RequestException:
            return _regs_unavailable()


def _regs_unavailable():
    return Response(
        {"detail": "AI service unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
    )
