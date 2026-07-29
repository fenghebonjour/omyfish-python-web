from django.urls import path

from .views import (
    BiteScoreForecastView,
    BiteScoreTodayView,
    IdentifyView,
    RegsAskView,
    RegsConsumptionStationsView,
    RegsConsumptionView,
    RegsLimitsView,
    RegsZonesGeoJsonView,
    SpeciesListView,
)

urlpatterns = [
    path("", SpeciesListView.as_view(), name="species-list"),
    path("/identify", IdentifyView.as_view(), name="species-identify"),
    path("/bite-score/today", BiteScoreTodayView.as_view(), name="species-bite-score-today"),
    path("/bite-score/forecast", BiteScoreForecastView.as_view(), name="species-bite-score-forecast"),
    path("/regs/limits", RegsLimitsView.as_view(), name="species-regs-limits"),
    path("/regs/zones/geojson", RegsZonesGeoJsonView.as_view(), name="species-regs-zones-geojson"),
    path(
        "/regs/consumption/stations",
        RegsConsumptionStationsView.as_view(),
        name="species-regs-consumption-stations",
    ),
    path("/regs/consumption", RegsConsumptionView.as_view(), name="species-regs-consumption"),
    path("/regs/ask", RegsAskView.as_view(), name="species-regs-ask"),
]
