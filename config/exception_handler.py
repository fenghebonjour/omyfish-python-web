import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    """Wraps DRF's default exception handler so a genuinely unhandled exception (a bug in a
    view, not an APIException/Http404/PermissionDenied DRF already turns into clean JSON)
    produces a structured 500 instead of falling through to Django's own error page — which is
    the DEBUG-mode HTML debug page whenever a prod deploy forgets to set DEBUG=False
    (BACKLOG.md item G, WEAKNESS_AUDIT.md §2.2).
    """
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    view = context.get("view")
    logger.exception("Unhandled exception in %s", view.__class__.__name__ if view else "view")
    return Response(
        {"error": "An unexpected error occurred."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
