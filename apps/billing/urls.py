from django.urls import path

from .views import CheckoutView, MeView

urlpatterns = [
    path("/me", MeView.as_view(), name="billing-me"),
    path("/checkout", CheckoutView.as_view(), name="billing-checkout"),
]
