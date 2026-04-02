"""Tests for the --json flag on the list_weekly_playlist management command."""

import json
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from houses.models import WeeklyPlaylist


class TestListWeeklyPlaylistJsonFlag(TestCase):
    def setUp(self) -> None:
        self.playlist = WeeklyPlaylist.objects.create(
            date=date(2026, 3, 30),
            youtube_playlist_id="PLtest123",
            youtube_playlist_url="https://www.youtube.com/playlist?list=PLtest123",
        )

    def test_json_output_contains_required_fields(self) -> None:
        out = StringIO()
        call_command("list_weekly_playlist", "2026-03-30", json=True, stdout=out)
        data = json.loads(out.getvalue())
        self.assertEqual(data["id"], self.playlist.id)
        self.assertEqual(data["date"], "2026-03-30")
        self.assertEqual(data["youtube_playlist_id"], "PLtest123")
        self.assertEqual(data["youtube_playlist_url"], "https://www.youtube.com/playlist?list=PLtest123")

    def test_json_output_is_valid_json(self) -> None:
        out = StringIO()
        call_command("list_weekly_playlist", "2026-03-30", json=True, stdout=out)
        # Should not raise
        json.loads(out.getvalue())

    def test_json_flag_omits_human_readable_header(self) -> None:
        out = StringIO()
        call_command("list_weekly_playlist", "2026-03-30", json=True, stdout=out)
        output = out.getvalue()
        self.assertNotIn("Weekly Playlist", output)
        self.assertNotIn("Total entries", output)

    def test_no_json_flag_produces_human_readable_output(self) -> None:
        out = StringIO()
        call_command("list_weekly_playlist", "2026-03-30", stdout=out)
        output = out.getvalue()
        self.assertIn("Weekly Playlist", output)

    def test_json_outputs_error_when_playlist_missing(self) -> None:
        out = StringIO()
        call_command("list_weekly_playlist", "2026-01-05", json=True, stdout=out)
        self.assertIn("No playlist found", out.getvalue())
