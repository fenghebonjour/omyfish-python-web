from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth", include("apps.accounts.urls")),
    path("api/v1/species", include("apps.species.urls")),
    path("api/v1/observations", include("apps.observations.urls")),
    path("api/v1/notifications", include("apps.notifications.urls")),
    path("api/v1/billing", include("apps.billing.urls")),
    path("api/v1/admin", include("apps.billing.admin_urls")),
]
