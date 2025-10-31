from django.core.management.base import BaseCommand
from houses.definitions import CrawlerCollectionState
from houses.models import LiveHouse


class Command(BaseCommand):
    help = "List all live houses with their collection status"

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        """List all live houses with ID, name, and last collection info."""  # noqa: C901, PLR0912, PLR0915, PLR0911
        live_houses = LiveHouse.objects.all().order_by("id")

        if not live_houses.exists():
            self.stdout.write(self.style.WARNING("No live houses found."))
            return

        self.stdout.write(f"Found {live_houses.count()} live houses:\n")

        # Header
        self.stdout.write(f"{'ID':<4} {'Name':<30} {'Last Collected':<20} {'Status':<10} {'Capacity':<8}")
        self.stdout.write("-" * 80)

        for live_house in live_houses:
            # Format last collected datetime
            if live_house.last_collected_datetime:
                last_collected = live_house.last_collected_datetime.strftime("%Y-%m-%d %H:%M")
            else:
                last_collected = "Never"

            # Format collection state
            state = live_house.last_collection_state or "pending"

            # Color code the status
            if state == CrawlerCollectionState.SUCCESS:
                status_display = self.style.SUCCESS(state)
            elif state == CrawlerCollectionState.ERROR:
                status_display = self.style.ERROR(state)
            elif state == CrawlerCollectionState.TIMEOUT:
                status_display = self.style.WARNING(state)
            else:
                status_display = state

            # Truncate name if too long
            name = live_house.name[:28] + ".." if len(live_house.name) > 30 else live_house.name  # noqa: PLR2004

            self.stdout.write(
                f"{live_house.id:<4} {name:<30} {last_collected:<20} {status_display:<10} {live_house.capacity:<8}"
            )

        self.stdout.write("")  # Empty line at the end
