"""Generate playlist introduction video for a given MonthlyPlaylist."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandParser
from houses.functions import generate_playlist_video
from houses.models import MonthlyPlaylist


class Command(BaseCommand):
    help = "Generate introduction video for a monthly playlist using AI"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "playlist_id",
            type=int,
            help="ID of the MonthlyPlaylist to generate video for",
        )
        parser.add_argument(
            "--intro-text-file",
            type=str,
            help="Path to UTF-8 text file containing pre-written introduction text",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN002, ANN003
        """Generate and save playlist introduction video."""
        playlist_id = options["playlist_id"]
        intro_text_file = options.get("intro_text_file")

        try:
            playlist = MonthlyPlaylist.objects.get(id=playlist_id)
        except MonthlyPlaylist.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"MonthlyPlaylist with id={playlist_id} not found"))
            return

        self.stdout.write(f"Generating video for playlist: {playlist.date.strftime('%B %Y')}")
        self.stdout.write(f"Playlist URL: {playlist.youtube_playlist_url}")

        # Load introduction text from file if provided
        intro_text = None
        if intro_text_file:
            intro_path = Path(intro_text_file)
            if not intro_path.exists():
                self.stderr.write(self.style.ERROR(f"Introduction text file not found: {intro_text_file}"))
                return
            try:
                intro_text = intro_path.read_text(encoding="utf-8")
                self.stdout.write(f"Using introduction text from: {intro_text_file}")
            except Exception as e:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"Failed to read introduction text file: {e}"))
                return
        else:
            self.stdout.write("Generating introduction text with AI...")

        self.stdout.write("")

        # Generate video
        video_filepath = generate_playlist_video(playlist, intro_text=intro_text)

        # Output the result
        self.stdout.write(self.style.SUCCESS("\n=== Video Generated ===\n"))
        self.stdout.write(f"Video saved to: {video_filepath}")
