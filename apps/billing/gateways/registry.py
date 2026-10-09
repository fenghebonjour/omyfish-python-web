from django.conf import settings

from .adyen_gateway import adyen_gateway
from .paypal_gateway import paypal_gateway
from .stripe_gateway import stripe_gateway

_GATEWAYS = {g.name: g for g in (stripe_gateway, paypal_gateway, adyen_gateway)}


def default_gateway():
    """None if the configured default isn't a known gateway name."""
    return _GATEWAYS.get(settings.PAYMENT_DEFAULT_PROCESSOR)


def exists(name):
    return name in _GATEWAYS


def by_name(name):
    """Raises KeyError for an unknown name — same "unconfigured is different from unknown"
    split the Java/dotnet siblings draw (checked by the caller via exists() first for the
    unknown case).
    """
    gateway = _GATEWAYS.get(name)
    if gateway is None:
        raise KeyError(f"Unknown payment processor: {name}")
    return gateway


def configured():
    return [g for g in _GATEWAYS.values() if g.is_configured()]
