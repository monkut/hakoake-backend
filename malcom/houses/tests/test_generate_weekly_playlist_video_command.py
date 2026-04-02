"""Tests for the generate_weekly_playlist_video management command."""

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from houses.models import WeeklyPlaylist


class TestGenerateWeeklyPlaylistVideoCommand(TestCase):
    def setUp(self) -> None:
        self.playlist = WeeklyPlaylist.objects.create(
            date=date(2026, 3, 30),
            youtube_playlist_id="PLtest123",
            youtube_playlist_url="https://www.youtube.com/playlist?list=PLtest123",
        )

    @patch("houses.management.commands.generate_weekly_playlist_video.insert_video_at_position")
    @patch("houses.management.commands.generate_weekly_playlist_video.upload_video_to_youtube")
    @patch("houses.management.commands.generate_weekly_playlist_video.generate_weekly_playlist_video")
    def test_uploads_and_inserts_at_position_zero_by_default(
        self, mock_gen: MagicMock, mock_upload: MagicMock, mock_insert: MagicMock
    ) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_video,
            tempfile.NamedTemporaryFile(suffix=".json") as tmp_secret,
        ):
            mock_gen.return_value = Path(tmp_video.name)
            mock_upload.return_value = "uploaded_vid_id"
            mock_insert.return_value = True

            call_command(
                "generate_weekly_playlist_video",
                str(self.playlist.id),
                secrets_file=tmp_secret.name,
            )

        mock_upload.assert_called_once()
        upload_args = mock_upload.call_args[0]
        self.assertEqual(upload_args[0], Path(tmp_video.name))
        self.assertIn("2026-03-30", upload_args[1])  # title contains week date

        mock_insert.assert_called_once()
        insert_args = mock_insert.call_args[0]
        self.assertEqual(insert_args[0], "PLtest123")  # playlist_id
        self.assertEqual(insert_args[1], "uploaded_vid_id")  # video_id
        self.assertEqual(insert_args[2], 0)  # position = first

    @patch("houses.management.commands.generate_weekly_playlist_video.insert_video_at_position")
    @patch("houses.management.commands.generate_weekly_playlist_video.upload_video_to_youtube")
    @patch("houses.management.commands.generate_weekly_playlist_video.generate_weekly_playlist_video")
    def test_skip_update_playlist_bypasses_upload_and_insert(
        self, mock_gen: MagicMock, mock_upload: MagicMock, mock_insert: MagicMock
    ) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_video:
            mock_gen.return_value = Path(tmp_video.name)
            call_command(
                "generate_weekly_playlist_video",
                str(self.playlist.id),
                skip_update_playlist=True,
            )

        mock_upload.assert_not_called()
        mock_insert.assert_not_called()

    @patch("houses.management.commands.generate_weekly_playlist_video.insert_video_at_position")
    @patch("houses.management.commands.generate_weekly_playlist_video.upload_video_to_youtube")
    @patch("houses.management.commands.generate_weekly_playlist_video.generate_weekly_playlist_video")
    def test_skips_upload_when_secrets_file_missing(
        self, mock_gen: MagicMock, mock_upload: MagicMock, mock_insert: MagicMock
    ) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_video:
            mock_gen.return_value = Path(tmp_video.name)
            call_command(
                "generate_weekly_playlist_video",
                str(self.playlist.id),
                secrets_file="/nonexistent/client_secret.json",
            )

        mock_upload.assert_not_called()
        mock_insert.assert_not_called()

    @patch("houses.management.commands.generate_weekly_playlist_video.generate_weekly_playlist_video")
    def test_error_when_playlist_not_found(self, mock_gen: MagicMock) -> None:
        from io import StringIO

        err = StringIO()
        call_command("generate_weekly_playlist_video", "99999", stderr=err)
        self.assertIn("not found", err.getvalue())
        mock_gen.assert_not_called()

    @patch("houses.management.commands.generate_weekly_playlist_video.insert_video_at_position")
    @patch("houses.management.commands.generate_weekly_playlist_video.upload_video_to_youtube")
    @patch("houses.management.commands.generate_weekly_playlist_video.generate_weekly_playlist_video")
    def test_skips_insert_when_upload_fails(
        self, mock_gen: MagicMock, mock_upload: MagicMock, mock_insert: MagicMock
    ) -> None:
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4") as tmp_video,
            tempfile.NamedTemporaryFile(suffix=".json") as tmp_secret,
        ):
            mock_gen.return_value = Path(tmp_video.name)
            mock_upload.side_effect = Exception("quota exceeded")
            call_command(
                "generate_weekly_playlist_video",
                str(self.playlist.id),
                secrets_file=tmp_secret.name,
            )

        mock_insert.assert_not_called()
