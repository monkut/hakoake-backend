from django.core.management.base import BaseCommand, CommandParser
from performers.models import Performer
from performers.youtube_search import search_and_create_performer_songs


class Command(BaseCommand):
    help = "Search YouTube for songs for performers that don't have any yet"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--performer-ids",
            nargs="+",
            type=int,
            help="Specific performer IDs to search for (if not provided, searches all without songs)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Search even for performers who already have songs",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be searched without actually searching",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003, C901, PLR0912, PLR0915, PLR0911
        """Search for YouTube videos for performers."""
        performer_ids = options.get("performer_ids")
        force = options["force"]
        dry_run = options["dry_run"]

        # Get performers to search for
        if performer_ids:
            performers = Performer.objects.filter(id__in=performer_ids)
            missing_ids = set(performer_ids) - set(performers.values_list("id", flat=True))
            if missing_ids:
                self.stdout.write(
                    self.style.WARNING(f"Performer IDs not found: {', '.join(map(str, sorted(missing_ids)))}")
                )
        # Get all performers without songs (or all if force is True)
        elif force:
            performers = Performer.objects.all()
        else:
            performers = Performer.objects.filter(songs__isnull=True)

        performers = performers.order_by("id")

        if not performers.exists():
            self.stdout.write(self.style.WARNING("No performers found to search for."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No searches will be performed\n"))

        self.stdout.write(f"Processing {performers.count()} performers:\n")

        success_count = 0
        failed_count = 0
        skipped_count = 0

        for performer in performers:
            # Check if performer already has songs (unless force is True)
            has_songs = performer.songs.exists()
            if has_songs and not force:
                self.stdout.write(f"⏭️  Skipping {performer.name} (ID: {performer.id}) - already has songs")
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(f"🔍 Would search YouTube for: {performer.name} (ID: {performer.id})")
                continue

            self.stdout.write(f"🔍 Searching YouTube for: {performer.name} (ID: {performer.id})")

            try:
                # Set flag to skip YouTube search in save method to avoid duplicate searches
                performer._skip_youtube_search = True
                songs = search_and_create_performer_songs(performer)

                if songs:
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Found {len(songs)} songs:"))
                    for i, song in enumerate(songs, 1):
                        self.stdout.write(
                            self.style.SUCCESS(f"      {i}. {song.title} ({song.youtube_view_count:,} views)")
                        )
                    success_count += 1
                else:
                    self.stdout.write("   ❌ No suitable videos found")
                    failed_count += 1

            except Exception as e:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"   ❌ Error searching for {performer.name}: {str(e)}"))
                failed_count += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDRY RUN: Would search for {performers.count()} performers."))
        else:
            self.stdout.write("\nSearch complete:")
            self.stdout.write(f"  ✅ Successful: {success_count}")
            self.stdout.write(f"  ❌ Failed: {failed_count}")
            self.stdout.write(f"  ⏭️  Skipped: {skipped_count}")
