"""Tests for the Instagram carousel publishing flow.

Covers the catbox upload helper and the end-to-end post_carousel orchestration
using mocked HTTP. Verifies that the deprecated rupload.facebook.com endpoint
is no longer referenced.
"""

from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase

from commons import instagram_post
from commons.instagram_post import (
    CatboxUploadError,
    InstagramContainerError,
    post_carousel,
    upload_to_catbox,
    wait_for_container_finished,
)


class TestUploadToCatbox(TestCase):
    @patch("commons.instagram_post.requests.post")
    def test_returns_https_url_on_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, text="https://files.catbox.moe/abc123.jpg\n")

        url = upload_to_catbox(b"\xff\xd8\xff\xe0fake-jpeg", "cover.jpg")

        self.assertEqual(url, "https://files.catbox.moe/abc123.jpg")
        mock_post.assert_called_once()
        _args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"], {"reqtype": "fileupload"})
        self.assertIn("fileToUpload", kwargs["files"])
        filename, _bytes, content_type = kwargs["files"]["fileToUpload"]
        self.assertEqual(filename, "cover.jpg")
        self.assertEqual(content_type, "image/jpeg")

    @patch("commons.instagram_post.requests.post")
    def test_raises_descriptive_error_on_http_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=500, text="Internal Server Error")

        with self.assertRaises(CatboxUploadError) as cm:
            upload_to_catbox(b"jpeg-bytes", "flyer_01.jpg")

        self.assertIn("flyer_01.jpg", str(cm.exception))
        self.assertIn("500", str(cm.exception))

    @patch("commons.instagram_post.requests.post")
    def test_raises_on_network_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = requests.ConnectionError("dns failure")

        with self.assertRaises(CatboxUploadError) as cm:
            upload_to_catbox(b"jpeg-bytes", "qr_02.jpg")

        self.assertIn("qr_02.jpg", str(cm.exception))
        self.assertIn("dns failure", str(cm.exception))

    @patch("commons.instagram_post.requests.post")
    def test_raises_when_response_is_not_https_url(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, text="something went wrong")

        with self.assertRaises(CatboxUploadError) as cm:
            upload_to_catbox(b"jpeg-bytes", "x.jpg")

        self.assertIn("x.jpg", str(cm.exception))


class TestWaitForContainerFinished(TestCase):
    @patch("commons.instagram_post.time.sleep", return_value=None)
    @patch("commons.instagram_post.requests.get")
    def test_returns_when_finished(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "FINISHED"},
            raise_for_status=lambda: None,
        )

        wait_for_container_finished("17999999", "tok")

        mock_get.assert_called_once()

    @patch("commons.instagram_post.time.sleep", return_value=None)
    @patch("commons.instagram_post.requests.get")
    def test_polls_until_finished(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        responses = [
            MagicMock(json=lambda: {"status_code": "IN_PROGRESS"}, raise_for_status=lambda: None),
            MagicMock(json=lambda: {"status_code": "IN_PROGRESS"}, raise_for_status=lambda: None),
            MagicMock(json=lambda: {"status_code": "FINISHED"}, raise_for_status=lambda: None),
        ]
        mock_get.side_effect = responses

        wait_for_container_finished("17999999", "tok")

        self.assertEqual(mock_get.call_count, 3)

    @patch("commons.instagram_post.time.sleep", return_value=None)
    @patch("commons.instagram_post.requests.get")
    def test_raises_on_error_status(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_get.return_value = MagicMock(
            json=lambda: {"status_code": "ERROR"},
            raise_for_status=lambda: None,
        )

        with self.assertRaises(InstagramContainerError) as cm:
            wait_for_container_finished("17999999", "tok")

        self.assertIn("ERROR", str(cm.exception))


class TestPostCarousel(TestCase):
    @patch("commons.instagram_post.publish_media", return_value="post-12345")
    @patch("commons.instagram_post.wait_for_container_finished", return_value=None)
    @patch("commons.instagram_post.create_carousel_container", return_value="parent-99")
    @patch("commons.instagram_post.create_carousel_item")
    @patch("commons.instagram_post.upload_to_catbox")
    def test_end_to_end_happy_path(
        self,
        mock_upload: MagicMock,
        mock_create_item: MagicMock,
        mock_create_container: MagicMock,
        mock_wait: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        mock_upload.side_effect = [
            "https://files.catbox.moe/cover.jpg",
            "https://files.catbox.moe/slide1.jpg",
            "https://files.catbox.moe/slide2.jpg",
        ]
        mock_create_item.side_effect = ["c1", "c2", "c3"]

        post_id = post_carousel(
            user_id="17841441683497898",
            access_token="tok",  # noqa: S106
            images=[
                (b"jpeg-cover", "cover.jpg"),
                (b"jpeg-slide1", "slide1.jpg"),
                (b"jpeg-slide2", "slide2.jpg"),
            ],
            caption="hello world",
        )

        self.assertEqual(post_id, "post-12345")
        self.assertEqual(mock_upload.call_count, 3)
        self.assertEqual(mock_create_item.call_count, 3)
        # Each child container is polled for FINISHED, plus the parent → 4 polls
        self.assertEqual(mock_wait.call_count, 4)
        mock_create_container.assert_called_once_with(
            "17841441683497898",
            "tok",
            ["c1", "c2", "c3"],
            "hello world",
        )
        mock_publish.assert_called_once_with("17841441683497898", "tok", "parent-99")

    def test_rejects_too_few_images(self) -> None:
        with self.assertRaises(ValueError):
            post_carousel("u", "t", [(b"x", "a.jpg")], "caption")

    def test_rejects_too_many_images(self) -> None:
        too_many = [(b"x", f"{i}.jpg") for i in range(11)]
        with self.assertRaises(ValueError):
            post_carousel("u", "t", too_many, "caption")


class TestRuploadEndpointRemoved(TestCase):
    """Regression: the video-only rupload endpoint and upload_image() must not return."""

    def test_no_upload_api_base_constant(self) -> None:
        # The old module exposed UPLOAD_API_BASE = "https://rupload.facebook.com/ig-api-upload"
        self.assertFalse(hasattr(instagram_post, "UPLOAD_API_BASE"))

    def test_upload_image_helper_removed(self) -> None:
        self.assertFalse(hasattr(instagram_post, "upload_image"))
