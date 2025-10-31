from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from houses.functions import collect_schedules


class Command(BaseCommand):
    help = "Collect schedules from all registered live house websites"

    def add_arguments(self, parser: CommandParser):  # noqa: ARG001
        """Add command-line arguments."""
        parser.add_argument(
            "--venue-id",
            type=int,
            help="Optional: Collect schedules only for the venue with this ID",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003, C901, PLR0912, PLR0915, PLR0911
        """Run the schedule collection process."""
        venue_id = options.get("venue_id")

        if venue_id:
            self.stdout.write(f"Starting schedule collection for venue ID: {venue_id}...\n")
        else:
            self.stdout.write("Starting schedule collection for all venues...\n")

        try:
            collect_schedules(venue_id=venue_id)
            self.stdout.write(self.style.SUCCESS("\nSchedule collection completed successfully!"))
        except Exception as e:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f"\nError during schedule collection: {str(e)}"))
            raise
