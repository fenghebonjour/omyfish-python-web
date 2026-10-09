from django.urls import path

from .views import CheckoutView, MeView, PaymentMethodSetupView, PortalSessionView, WebhookView

urlpatterns = [
    path("/me", MeView.as_view(), name="billing-me"),
    path("/checkout", CheckoutView.as_view(), name="billing-checkout"),
    path("/payment-method/setup", PaymentMethodSetupView.as_view(), name="billing-payment-method-setup"),
    path("/portal-session", PortalSessionView.as_view(), name="billing-portal-session"),
    path("/webhook/<str:processor>", WebhookView.as_view(), name="billing-webhook"),
]
