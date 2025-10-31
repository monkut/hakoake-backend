from datetime import timedelta

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils import timezone
from django.utils.feedgenerator import Rss201rev2Feed

from .models import PerformanceSchedule


class LatestPerformancesFeed(Feed):
    """RSS feed for latest performance schedules."""

    title = "Latest Performance Schedules"
    link = "/schedule/"
    description = "Latest upcoming performances at live houses"
    feed_type = Rss201rev2Feed

    def items(self):
        """Return the latest 50 upcoming performances."""
        today = timezone.now().date()
        return (
            PerformanceSchedule.objects.filter(performance_date__gte=today)
            .select_related("live_house")
            .prefetch_related("performers")
            .order_by("performance_date", "start_time")[:50]
        )

    def item_title(self, item: PerformanceSchedule) -> str:
        """Return the title for each item."""
        if item.performance_name:
            return f"{item.performance_name} at {item.live_house.name}"
        return f"Performance at {item.live_house.name}"

    def item_description(self, item: PerformanceSchedule) -> str:
        """Return the description for each item."""
        description_parts = []

        # Add performance name if available
        if item.performance_name:
            description_parts.append(f"Event: {item.performance_name}")

        # Add venue information
        description_parts.append(f"Venue: {item.live_house.name}")

        # Add date and time information
        description_parts.append(f"Date: {item.performance_date.strftime('%Y-%m-%d')}")
        description_parts.append(f"Doors: {item.open_time.strftime('%H:%M')}")
        description_parts.append(f"Start: {item.start_time.strftime('%H:%M')}")

        # Add pricing information
        if item.presale_price:
            description_parts.append(f"Presale: ¥{item.presale_price:,.0f}")
        if item.door_price:
            description_parts.append(f"Door: ¥{item.door_price:,.0f}")

        # Add performers
        performers = list(item.performers.all())
        if performers:
            performer_names = ", ".join([performer.name for performer in performers])
            description_parts.append(f"Performers: {performer_names}")

        # Add venue details
        description_parts.append(f"Address: {item.live_house.address}")
        description_parts.append(f"Capacity: {item.live_house.capacity}")

        # Add ticket information if available
        if hasattr(item, "ticket_purchase_info") and item.ticket_purchase_info:
            ticket_info = item.ticket_purchase_info
            if ticket_info.ticket_url:
                description_parts.append(f"Tickets: {ticket_info.ticket_url}")
            if ticket_info.ticket_contact_email:
                description_parts.append(f"Contact: {ticket_info.ticket_contact_email}")

        return "\n".join(description_parts)

    def item_link(self, item: PerformanceSchedule) -> str:
        """Return the link for each item."""
        return reverse("houses:schedule_month", args=[item.performance_date.year, item.performance_date.month])

    def item_pubdate(self, item: PerformanceSchedule) -> timezone.datetime:
        """Return the publication date for each item."""
        # Use the created_datetime if available, otherwise use a default
        if hasattr(item, "created_datetime") and item.created_datetime:
            return item.created_datetime
        # Fallback to current time minus days until performance date
        days_until = (item.performance_date - timezone.now().date()).days
        return timezone.now() - timedelta(days=max(0, days_until))

    def item_guid(self, item: PerformanceSchedule) -> str:
        """Return a unique GUID for each item."""
        return f"performance-{item.id}-{item.performance_date}-{item.start_time}"
