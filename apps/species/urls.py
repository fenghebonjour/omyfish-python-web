from django.urls import path

from .views import BiteScoreForecastView, BiteScoreTodayView, IdentifyView, SpeciesListView

urlpatterns = [
    path("", SpeciesListView.as_view(), name="species-list"),
    path("/identify", IdentifyView.as_view(), name="species-identify"),
    path("/bite-score/today", BiteScoreTodayView.as_view(), name="species-bite-score-today"),
    path("/bite-score/forecast", BiteScoreForecastView.as_view(), name="species-bite-score-forecast"),
]
