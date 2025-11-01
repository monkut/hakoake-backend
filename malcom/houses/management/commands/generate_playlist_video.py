"""Generate playlist introduction video for a given MonthlyPlaylist."""

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

    def handle(self, *args, **options) -> None:  # noqa: ANN002, ANN003
        """Generate and save playlist introduction video."""
        playlist_id = options["playlist_id"]

        try:
            playlist = MonthlyPlaylist.objects.get(id=playlist_id)
        except MonthlyPlaylist.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"MonthlyPlaylist with id={playlist_id} not found"))
            return

        self.stdout.write(f"Generating video for playlist: {playlist.date.strftime('%B %Y')}")
        self.stdout.write(f"Playlist URL: {playlist.youtube_playlist_url}")
        self.stdout.write("")

        # Generate video
        video_filepath = generate_playlist_video(playlist)

        # Output the result
        self.stdout.write(self.style.SUCCESS("\n=== Video Generated ===\n"))
        self.stdout.write(f"Video saved to: {video_filepath}")
