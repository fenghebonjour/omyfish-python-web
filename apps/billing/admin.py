from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "status", "plan", "trial_end", "current_period_end"]
    list_filter = ["status", "plan"]
