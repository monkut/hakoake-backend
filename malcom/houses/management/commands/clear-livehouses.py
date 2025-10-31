from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from houses.definitions import CrawlerCollectionState
from houses.models import LiveHouse


class Command(BaseCommand):
    help = "Clear last collection data for specified live houses"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "livehouse_ids", nargs="+", type=int, help="IDs of live houses to clear collection data for"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleared without actually clearing",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        """Clear last collection data for the specified live house IDs."""  # noqa: C901, PLR0912, PLR0915, PLR0911
        livehouse_ids = options["livehouse_ids"]
        dry_run = options["dry_run"]

        # Validate that all IDs exist
        live_houses = LiveHouse.objects.filter(id__in=livehouse_ids)
        found_ids = set(live_houses.values_list("id", flat=True))
        missing_ids = set(livehouse_ids) - found_ids

        if missing_ids:
            raise CommandError(f"Live house IDs not found: {', '.join(map(str, sorted(missing_ids)))}")  # noqa: B904

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))

        self.stdout.write(f"Processing {live_houses.count()} live houses:\n")

        # Show what will be cleared
        for live_house in live_houses.order_by("id"):
            last_collected = (
                live_house.last_collected_datetime.strftime("%Y-%m-%d %H:%M")
                if live_house.last_collected_datetime
                else "Never"
            )
            state = live_house.last_collection_state or "pending"

            self.stdout.write(
                f"ID {live_house.id}: {live_house.name}\n"
                f"  Current: Last collected {last_collected}, Status: {state}\n"
                f"  {'Would clear' if dry_run else 'Clearing'}: last_collected_datetime and last_collection_state"
            )
            self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: No actual changes were made."))
            return

        # Confirm before proceeding
        if options.get("verbosity", 1) != 0:  # Skip confirmation in quiet mode
            confirm = input("Do you want to proceed? [y/N]: ")
            if confirm.lower() not in ["y", "yes"]:
                self.stdout.write("Operation cancelled.")
                return

        # Clear the collection data
        with transaction.atomic():
            cleared_count = 0
            for live_house in live_houses:
                live_house.last_collected_datetime = None
                live_house.last_collection_state = CrawlerCollectionState.PENDING
                live_house.save(update_fields=["last_collected_datetime", "last_collection_state"])
                cleared_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully cleared collection data for {cleared_count} live houses."))
