from django.urls import path

from .admin_views import ExtendTrialView, GrantView, RevokeView, StatsView, SubscriptionListView

urlpatterns = [
    path("/stats", StatsView.as_view(), name="admin-stats"),
    path("/subscriptions", SubscriptionListView.as_view(), name="admin-subscriptions"),
    path("/subscriptions/<uuid:user_id>/grant", GrantView.as_view(), name="admin-subscriptions-grant"),
    path("/subscriptions/<uuid:user_id>/revoke", RevokeView.as_view(), name="admin-subscriptions-revoke"),
    path(
        "/subscriptions/<uuid:user_id>/extend-trial",
        ExtendTrialView.as_view(),
        name="admin-subscriptions-extend-trial",
    ),
]
