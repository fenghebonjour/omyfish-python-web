from django.urls import path

from .views import ObservationDeleteView, ObservationGeoJSONView, ObservationListCreateView

urlpatterns = [
    path("", ObservationListCreateView.as_view(), name="observations-list-create"),
    path("/geojson", ObservationGeoJSONView.as_view(), name="observations-geojson"),
    path("/<uuid:observation_id>", ObservationDeleteView.as_view(), name="observations-delete"),
]
