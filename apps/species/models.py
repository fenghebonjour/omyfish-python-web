from django.db import models


class Species(models.Model):
    # `key` mirrors the class-folder / species-key convention used by
    # omyfish-ai (see fish_info.json + /bite-score/species-key).
    key = models.SlugField(unique=True)
    common_name = models.CharField(max_length=255)
    scientific_name = models.CharField(max_length=255, blank=True, null=True)
    habitat = models.TextField(blank=True, null=True)
    diet = models.TextField(blank=True, null=True)
    max_size_cm = models.FloatField(blank=True, null=True)
    conservation_status = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    fun_fact = models.TextField(blank=True, null=True)
    # Curated flag — seeding defaults this to False; mark true per the MFFP
    # Quebec freshwater/migratory atlas list as species are curated.
    north_american_freshwater = models.BooleanField(default=False)

    class Meta:
        ordering = ["common_name"]

    def __str__(self):
        return self.common_name
