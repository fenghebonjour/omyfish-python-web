import json
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.species.models import Species

DEFAULT_SOURCE = settings.BASE_DIR / "../omyfish-python/data/metadata/fish_info.json"


def slugify_key(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


class Command(BaseCommand):
    help = "Seed the Species table from omyfish-python's fish_info.json knowledge base"

    def add_arguments(self, parser):
        parser.add_argument("--source", default=str(DEFAULT_SOURCE))

    def handle(self, *args, **options):
        with open(options["source"]) as f:
            entries = json.load(f)

        created, updated = 0, 0
        for entry in entries:
            key = slugify_key(entry["species"])
            _, was_created = Species.objects.update_or_create(
                key=key,
                defaults={
                    "common_name": entry["species"].replace("_", " ").title(),
                    "scientific_name": entry.get("scientific_name"),
                    "habitat": entry.get("habitat"),
                    "diet": entry.get("diet"),
                    "max_size_cm": entry.get("max_size_cm"),
                    "conservation_status": entry.get("conservation_status"),
                    "description": entry.get("description"),
                    "fun_fact": entry.get("fun_fact"),
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(f"Seeded species: {created} created, {updated} updated"))
