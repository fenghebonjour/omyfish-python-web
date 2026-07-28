from django.contrib import admin

from .models import Observation


@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ["species_name", "user", "latitude", "longitude", "observed_at"]
    list_filter = ["source"]
