"""Fix MonthlyPlaylistEntry positions to be sequential with spotlight performers last."""

from argparse import ArgumentParser

from django.core.management.base import BaseCommand
from django.db import transaction
from houses.models import MonthlyPlaylist


class Command(BaseCommand):
    help = "Fix playlist entry positions to be sequential (1, 2, 3...) with spotlight performers last"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--playlist-id",
            type=int,
            help="Fix positions for a specific playlist (default: all playlists)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN002, ANN003, PLR0912
        """Fix positions for all or specific playlists."""
        dry_run = options["dry_run"]
        playlist_id = options.get("playlist_id")

        if playlist_id:
            playlists = MonthlyPlaylist.objects.filter(id=playlist_id)
            if not playlists.exists():
                self.stderr.write(self.style.ERROR(f"Playlist with id={playlist_id} not found"))
                return
        else:
            playlists = MonthlyPlaylist.objects.all()

        total_fixed = 0

        for playlist in playlists:
            self.stdout.write(f"\nProcessing: {playlist.date.strftime('%B %Y')}")

            # Get all entries for this playlist
            entries = list(playlist.monthlyplaylistentry_set.all())

            if not entries:
                self.stdout.write("  No entries found")
                continue

            # Separate regular and spotlight performers
            regular_entries = [e for e in entries if not e.is_spotlight]
            spotlight_entries = [e for e in entries if e.is_spotlight]

            # Sort by current position to preserve order
            regular_entries.sort(key=lambda x: x.position)
            spotlight_entries.sort(key=lambda x: x.position)

            # Combine in order: regular first, spotlight last
            ordered_entries = regular_entries + spotlight_entries

            # Show current and new positions
            changes_needed = False
            for idx, entry in enumerate(ordered_entries, start=1):
                new_position = idx
                if entry.position != new_position:
                    changes_needed = True
                    self.stdout.write(
                        f"  {entry.song.performer.name}: "
                        f"position {entry.position} → {new_position} "
                        f"(spotlight={entry.is_spotlight})"
                    )

            if not changes_needed:
                self.stdout.write("  No changes needed")
                continue

            # Apply changes
            if not dry_run:
                # Update positions using queryset update to bypass save() method
                with transaction.atomic():
                    # First, move all entries to high positions to avoid unique constraint violations
                    for idx, entry in enumerate(ordered_entries, start=1):
                        # Set to temporary high position (1000 + idx)
                        entry.__class__.objects.filter(pk=entry.pk).update(position=1000 + idx)

                    # Then set final positions
                    for idx, entry in enumerate(ordered_entries, start=1):
                        entry.__class__.objects.filter(pk=entry.pk).update(position=idx)

                total_fixed += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Fixed {len(ordered_entries)} entries"))
            else:
                self.stdout.write("  (dry run - no changes made)")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n{total_fixed} playlist(s) would be fixed (dry run mode)"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Fixed {total_fixed} playlist(s)"))
