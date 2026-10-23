"""Tests for shared utilities in commons.functions."""

from unittest.mock import MagicMock, patch

import requests
from django.conf import settings
from django.test import TestCase, override_settings

from commons.functions import (
    IMAGE_HOST_PROVIDERS_AVAILABLE,
    LITTERBOX_API_URL,
    LITTERBOX_TTL,
    UGUU_API_URL,
    ImageHostUploadError,
    LitterboxUploadError,
    UguuUploadError,
    upload_to_litterbox,
    upload_to_public_image_host,
    upload_to_uguu,
)


class TestUploadToLitterbox(TestCase):
    @patch("commons.functions.requests.post")
    def test_returns_https_url_on_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, text="https://litter.catbox.moe/abc123.jpg\n")

        url = upload_to_litterbox(b"\xff\xd8\xff\xe0fake-jpeg", "cover.jpg")

        self.assertEqual(url, "https://litter.catbox.moe/abc123.jpg")
        mock_post.assert_called_once()
        _args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"], {"reqtype": "fileupload", "time": LITTERBOX_TTL})
        self.assertIn("fileToUpload", kwargs["files"])
        filename, _bytes, content_type = kwargs["files"]["fileToUpload"]
        self.assertEqual(filename, "cover.jpg")
        self.assertEqual(content_type, "image/jpeg")

    @patch("commons.functions.requests.post")
    def test_sends_time_field_as_1h(self, mock_post: MagicMock) -> None:
        """Regression: litterbox requires the ``time`` field; omission yields HTTP 400."""
        mock_post.return_value = MagicMock(status_code=200, text="https://litter.catbox.moe/abc123.jpg")

        upload_to_litterbox(b"jpeg-bytes", "flyer.jpg")

        _args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"].get("time"), "1h")

    @patch("commons.functions.requests.post")
    def test_raises_descriptive_error_on_http_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")

        with self.assertRaises(LitterboxUploadError) as cm:
            upload_to_litterbox(b"jpeg-bytes", "flyer_01.jpg")

        self.assertIn("flyer_01.jpg", str(cm.exception))
        self.assertIn("500", str(cm.exception))

    @patch("commons.functions.requests.post")
    def test_raises_on_network_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = requests.ConnectionError("dns failure")

        with self.assertRaises(LitterboxUploadError) as cm:
            upload_to_litterbox(b"jpeg-bytes", "qr_02.jpg")

        self.assertIn("qr_02.jpg", str(cm.exception))
        self.assertIn("dns failure", str(cm.exception))

    @patch("commons.functions.requests.post")
    def test_raises_when_response_is_not_https_url(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, text="something went wrong")

        with self.assertRaises(LitterboxUploadError) as cm:
            upload_to_litterbox(b"jpeg-bytes", "x.jpg")

        self.assertIn("x.jpg", str(cm.exception))


class TestUploadToUguu(TestCase):
    @patch("commons.functions.requests.post")
    def test_returns_https_url_on_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "files": [{"url": "https://d.uguu.se/abc123.jpg", "size": 3}]},
        )

        url = upload_to_uguu(b"\xff\xd8\xff\xe0fake-jpeg", "cover.jpg")

        self.assertEqual(url, "https://d.uguu.se/abc123.jpg")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], UGUU_API_URL)
        self.assertIn("files[]", kwargs["files"])
        filename, _bytes, content_type = kwargs["files"]["files[]"]
        self.assertEqual(filename, "cover.jpg")
        self.assertEqual(content_type, "image/jpeg")

    @patch("commons.functions.requests.post")
    def test_guesses_content_type_from_filename(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"success": True, "files": [{"url": "https://d.uguu.se/story.mp4"}]},
        )

        upload_to_uguu(b"mp4-bytes", "story_20261019.mp4")

        _args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["files"]["files[]"][2], "video/mp4")

    @patch("commons.functions.requests.post")
    def test_raises_descriptive_error_on_http_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=503, text="Service Unavailable")

        with self.assertRaises(UguuUploadError) as cm:
            upload_to_uguu(b"jpeg-bytes", "flyer_01.jpg")

        self.assertIn("flyer_01.jpg", str(cm.exception))
        self.assertIn("503", str(cm.exception))

    @patch("commons.functions.requests.post")
    def test_raises_on_network_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = requests.ConnectionError("dns failure")

        with self.assertRaises(UguuUploadError) as cm:
            upload_to_uguu(b"jpeg-bytes", "qr_02.jpg")

        self.assertIn("qr_02.jpg", str(cm.exception))
        self.assertIn("dns failure", str(cm.exception))

    @patch("commons.functions.requests.post")
    def test_raises_when_response_is_not_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"success": False, "errorcode": 400})

        with self.assertRaises(UguuUploadError) as cm:
            upload_to_uguu(b"jpeg-bytes", "x.jpg")

        self.assertIn("x.jpg", str(cm.exception))

    @patch("commons.functions.requests.post")
    def test_raises_when_response_is_not_json(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, json=MagicMock(side_effect=ValueError("no json")))

        with self.assertRaises(UguuUploadError):
            upload_to_uguu(b"jpeg-bytes", "x.jpg")

    @patch("commons.functions.requests.post")
    def test_raises_when_url_is_not_https(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200, json=lambda: {"success": True, "files": [{"url": "http://d.uguu.se/abc.jpg"}]}
        )

        with self.assertRaises(UguuUploadError):
            upload_to_uguu(b"jpeg-bytes", "x.jpg")


class TestUploadToPublicImageHost(TestCase):
    def test_litterbox_error_is_an_image_host_error(self) -> None:
        """Backward compatibility: callers catching LitterboxUploadError keep working."""
        self.assertTrue(issubclass(LitterboxUploadError, ImageHostUploadError))
        self.assertTrue(issubclass(UguuUploadError, ImageHostUploadError))

    @patch("commons.functions.upload_to_uguu")
    @patch("commons.functions.upload_to_litterbox", return_value="https://litter.catbox.moe/ok.jpg")
    def test_first_provider_success_skips_rest(self, mock_litterbox: MagicMock, mock_uguu: MagicMock) -> None:
        url = upload_to_public_image_host(b"jpeg", "cover.jpg", providers=("litterbox", "uguu"))

        self.assertEqual(url, "https://litter.catbox.moe/ok.jpg")
        mock_litterbox.assert_called_once_with(b"jpeg", "cover.jpg")
        mock_uguu.assert_not_called()

    @patch("commons.functions.upload_to_uguu", return_value="https://d.uguu.se/ok.jpg")
    @patch("commons.functions.upload_to_litterbox", side_effect=LitterboxUploadError("HTTP 500"))
    def test_falls_back_and_logs_warning(self, mock_litterbox: MagicMock, mock_uguu: MagicMock) -> None:
        with self.assertLogs("commons.functions", level="WARNING") as logs:
            url = upload_to_public_image_host(b"jpeg", "cover.jpg", providers=("litterbox", "uguu"))

        self.assertEqual(url, "https://d.uguu.se/ok.jpg")
        mock_litterbox.assert_called_once()
        mock_uguu.assert_called_once_with(b"jpeg", "cover.jpg")
        self.assertEqual(len(logs.records), 1)
        self.assertIn("litterbox", logs.output[0])
        self.assertIn("HTTP 500", logs.output[0])

    @patch("commons.functions.upload_to_uguu", side_effect=UguuUploadError("HTTP 503"))
    @patch("commons.functions.upload_to_litterbox", side_effect=LitterboxUploadError("HTTP 412"))
    def test_all_providers_fail_raises_aggregate_error(self, mock_litterbox: MagicMock, mock_uguu: MagicMock) -> None:
        with self.assertRaises(ImageHostUploadError) as cm:
            upload_to_public_image_host(b"jpeg", "cover.jpg", providers=("litterbox", "uguu"))

        message = str(cm.exception)
        self.assertIn("cover.jpg", message)
        self.assertIn("litterbox", message)
        self.assertIn("HTTP 412", message)
        self.assertIn("uguu", message)
        self.assertIn("HTTP 503", message)
        self.assertIsInstance(cm.exception.__cause__, UguuUploadError)

    @patch("commons.functions.upload_to_uguu", return_value="https://d.uguu.se/ok.jpg")
    @patch("commons.functions.upload_to_litterbox", side_effect=LitterboxUploadError("HTTP 412"))
    def test_each_provider_is_tried_once_per_call(self, mock_litterbox: MagicMock, mock_uguu: MagicMock) -> None:
        upload_to_public_image_host(b"jpeg", "cover.jpg", providers=("litterbox", "uguu"))

        self.assertEqual(mock_litterbox.call_count, 1)
        self.assertEqual(mock_uguu.call_count, 1)

    def test_unknown_provider_name_is_a_configuration_error(self) -> None:
        with self.assertRaises(ValueError) as cm:
            upload_to_public_image_host(b"jpeg", "cover.jpg", providers=("litterbox", "imgur"))

        self.assertIn("imgur", str(cm.exception))

    def test_empty_provider_list_is_a_configuration_error(self) -> None:
        with self.assertRaises(ValueError):
            upload_to_public_image_host(b"jpeg", "cover.jpg", providers=())

    @override_settings(IMAGE_HOST_PROVIDERS=("uguu",))
    @patch("commons.functions.upload_to_uguu", return_value="https://d.uguu.se/ok.jpg")
    @patch("commons.functions.upload_to_litterbox")
    def test_default_providers_come_from_settings(self, mock_litterbox: MagicMock, mock_uguu: MagicMock) -> None:
        url = upload_to_public_image_host(b"jpeg", "cover.jpg")

        self.assertEqual(url, "https://d.uguu.se/ok.jpg")
        mock_litterbox.assert_not_called()

    def test_default_setting_starts_with_litterbox_and_has_an_independent_fallback(self) -> None:
        self.assertEqual(settings.IMAGE_HOST_PROVIDERS[0], "litterbox")
        self.assertIn("uguu", settings.IMAGE_HOST_PROVIDERS)
        self.assertTrue(set(settings.IMAGE_HOST_PROVIDERS) <= set(IMAGE_HOST_PROVIDERS_AVAILABLE))

    @patch("commons.functions.requests.post")
    def test_regression_2026_04_13_anon_uploads_paused(self, mock_post: MagicMock) -> None:
        """Regression for the 2026-04-13 incident: the primary host answers 412, the fallback serves the URL."""

        def fake_post(url: str, **_kwargs: object) -> MagicMock:
            if url == LITTERBOX_API_URL:
                return MagicMock(status_code=412, text="Anon Uploads are temporarily paused due to abuse!")
            return MagicMock(
                status_code=200, json=lambda: {"success": True, "files": [{"url": "https://d.uguu.se/ok.jpg"}]}
            )

        mock_post.side_effect = fake_post

        url = upload_to_public_image_host(b"jpeg", "cover.jpg", providers=("litterbox", "uguu"))

        self.assertEqual(url, "https://d.uguu.se/ok.jpg")
        self.assertEqual(mock_post.call_count, 2)
