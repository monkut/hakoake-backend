"""Tests for upload_video_to_youtube and insert_video_at_position in youtube_utils."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase


class TestUploadVideoToYoutube(TestCase):
    @patch("commons.youtube_utils.get_authorized_youtube_client")
    @patch("commons.youtube_utils.googleapiclient.http.MediaFileUpload")
    def test_returns_video_id(self, mock_media_upload: MagicMock, mock_get_client: MagicMock) -> None:
        from commons.youtube_utils import upload_video_to_youtube

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {"id": "abc123"})
        mock_youtube.videos.return_value.insert.return_value = mock_request

        video_id = upload_video_to_youtube(
            video_path=Path("/tmp/intro.mp4"),  # noqa: S108
            title="Test Video",
            description="A test",
            client_secrets_file=Path("/tmp/client_secret.json"),  # noqa: S108
        )

        self.assertEqual(video_id, "abc123")

    @patch("commons.youtube_utils.get_authorized_youtube_client")
    @patch("commons.youtube_utils.googleapiclient.http.MediaFileUpload")
    def test_logs_progress_when_status_present(self, mock_media_upload: MagicMock, mock_get_client: MagicMock) -> None:
        from commons.youtube_utils import upload_video_to_youtube

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_status = MagicMock()
        mock_status.progress.return_value = 0.5

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = [
            (mock_status, None),
            (None, {"id": "xyz789"}),
        ]
        mock_youtube.videos.return_value.insert.return_value = mock_request

        video_id = upload_video_to_youtube(
            video_path=Path("/tmp/intro.mp4"),  # noqa: S108
            title="Test",
            description="desc",
            client_secrets_file=Path("/tmp/client_secret.json"),  # noqa: S108
        )

        self.assertEqual(video_id, "xyz789")

    @patch("commons.youtube_utils.get_authorized_youtube_client")
    @patch("commons.youtube_utils.googleapiclient.http.MediaFileUpload")
    def test_uses_provided_privacy_status(self, mock_media_upload: MagicMock, mock_get_client: MagicMock) -> None:
        from commons.youtube_utils import upload_video_to_youtube

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {"id": "priv1"})
        mock_youtube.videos.return_value.insert.return_value = mock_request

        upload_video_to_youtube(
            video_path=Path("/tmp/intro.mp4"),  # noqa: S108
            title="T",
            description="D",
            client_secrets_file=Path("/tmp/client_secret.json"),  # noqa: S108
            privacy_status="private",
        )

        call_kwargs = mock_youtube.videos.return_value.insert.call_args[1]
        self.assertEqual(call_kwargs["body"]["status"]["privacyStatus"], "private")


class TestInsertVideoAtPosition(TestCase):
    @patch("commons.youtube_utils.get_authorized_youtube_client")
    def test_returns_true_on_success(self, mock_get_client: MagicMock) -> None:
        from commons.youtube_utils import insert_video_at_position

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        result = insert_video_at_position("PL123", "vid456", 0, Path("/tmp/client_secret.json"))  # noqa: S108

        self.assertTrue(result)
        mock_youtube.playlistItems.return_value.insert.assert_called_once()
        call_body = mock_youtube.playlistItems.return_value.insert.call_args[1]["body"]
        self.assertEqual(call_body["snippet"]["position"], 0)
        self.assertEqual(call_body["snippet"]["playlistId"], "PL123")
        self.assertEqual(call_body["snippet"]["resourceId"]["videoId"], "vid456")

    @patch("commons.youtube_utils.get_authorized_youtube_client")
    def test_returns_false_on_http_error(self, mock_get_client: MagicMock) -> None:
        import googleapiclient.errors

        from commons.youtube_utils import insert_video_at_position

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        mock_resp = MagicMock()
        mock_resp.status = 403
        mock_resp.reason = "Forbidden"
        mock_youtube.playlistItems.return_value.insert.return_value.execute.side_effect = (
            googleapiclient.errors.HttpError(mock_resp, b"Forbidden")
        )

        result = insert_video_at_position("PL123", "vid456", 0, Path("/tmp/client_secret.json"))  # noqa: S108

        self.assertFalse(result)

    @patch("commons.youtube_utils.get_authorized_youtube_client")
    def test_inserts_at_specified_position(self, mock_get_client: MagicMock) -> None:
        from commons.youtube_utils import insert_video_at_position

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        insert_video_at_position("PL999", "vidABC", 3, Path("/tmp/client_secret.json"))  # noqa: S108

        call_body = mock_youtube.playlistItems.return_value.insert.call_args[1]["body"]
        self.assertEqual(call_body["snippet"]["position"], 3)
