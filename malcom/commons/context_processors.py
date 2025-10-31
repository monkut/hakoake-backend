from django.conf import settings
from django.http.request import HttpRequest


def global_view_additional_context(_: HttpRequest) -> dict:
    """Context defined here is provided additionally to the template rendering context"""
    context = {
        "URL_PREFIX": settings.URL_PREFIX,
        "STATIC_URL": settings.STATIC_URL,
    }
    return context
