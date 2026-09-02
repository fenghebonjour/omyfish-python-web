from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth", include("apps.accounts.urls")),
    path("api/v1/species", include("apps.species.urls")),
    path("api/v1/observations", include("apps.observations.urls")),
    path("api/v1/notifications", include("apps.notifications.urls")),
    path("api/v1/billing", include("apps.billing.urls")),
    path("api/v1/admin", include("apps.billing.admin_urls")),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
