from django.urls import path
from django_distill import distill_path

from . import views
from .feeds import LatestPerformancesFeed

app_name = "houses"


def get_empty_list():
    """Return empty list for parameterless URLs."""
    return [None]


urlpatterns = [
    # Regular Django URLs for testing
    path("schedule/", views.current_month_view, name="schedule_current"),
    path("schedule/<int:year>/<int:month>/", views.performance_schedule_view, name="schedule_month"),
    path("performer/<int:performer_id>/", views.performer_detail_view, name="performer_detail"),
    path("venue/<int:venue_id>/", views.venue_detail_view, name="venue_detail"),
    path("latest-rss.xml", LatestPerformancesFeed(), name="latest_rss"),
]

# Django-distill URL patterns for static generation
distill_urlpatterns = [
    distill_path(
        "static/schedule/<int:year>/<int:month>/",
        views.performance_schedule_view,
        name="schedule_month_distill",
        distill_func=views.get_month_urls,
    ),
    distill_path(
        "static/schedule/", views.current_month_view, name="schedule_current_distill", distill_func=get_empty_list
    ),
    distill_path(
        "static/performer/<int:performer_id>/",
        views.performer_detail_view,
        name="performer_detail_distill",
        distill_func=views.get_performer_urls,
    ),
    distill_path(
        "static/venue/<int:venue_id>/",
        views.venue_detail_view,
        name="venue_detail_distill",
        distill_func=views.get_venue_urls,
    ),
    distill_path(
        "static/latest-rss.xml",
        LatestPerformancesFeed(),
        name="latest_rss_distill",
        distill_func=get_empty_list,
    ),
]
