from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.billing import services


class Command(BaseCommand):
    """Runs the same reconciliation job as POST /api/v1/admin/subscriptions/reconcile — a
    periodic management command is the natural fit for this in Django (unlike Java's Spring
    @Scheduled or dotnet's admin-triggered-only endpoint), meant to be run from cron/Celery
    beat/a Kubernetes CronJob.
    """

    help = "Repairs local subscription rows whose payment-processor link never got saved."

    def add_arguments(self, parser):
        parser.add_argument("--lookback-hours", type=int, default=24)

    def handle(self, *args, **options):
        since = timezone.now() - timezone.timedelta(hours=options["lookback_hours"])
        result = services.reconcile(since)

        self.stdout.write(f"Checked {result['checked']} subscription(s).")
        for line in result["repaired"]:
            self.stdout.write(self.style.SUCCESS(f"Repaired: {line}"))
        for line in result["errors"]:
            self.stderr.write(self.style.WARNING(line))
