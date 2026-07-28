from django.contrib import admin

from .models import Species


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ["key", "common_name", "scientific_name", "north_american_freshwater"]
    list_filter = ["north_american_freshwater"]
    search_fields = ["key", "common_name", "scientific_name"]
