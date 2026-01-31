"""
Fetch performer images from TheAudioDB and other sources.

Integrated from the standalone artist_image_fetcher.py script.
"""

import logging
from io import BytesIO
from typing import TYPE_CHECKING

import requests
from django.core.files.base import ContentFile

if TYPE_CHECKING:
    from .models import Performer

logger = logging.getLogger(__name__)


class PerformerImageFetcher:
    """Fetches performer images and logos from TheAudioDB API."""

    # TheAudioDB API (free tier)
    TADB_API_KEY = "2"  # Public test key
    TADB_SEARCH_URL = "https://www.theaudiodb.com/api/v1/json/{api_key}/search.php"

    def __init__(self) -> None:
        """Initialize the fetcher with a requests session."""
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "PerformerImageFetcher/1.0"})

    def search_theaudiodb(self, artist_name: str) -> dict[str, str | None]:
        """
        Search TheAudioDB for artist information and image URLs.

        Args:
            artist_name: Name of the artist to search for

        Returns:
            Dictionary with image URLs (thumb, logo, fanart, banner) or empty dict
        """
        try:
            url = self.TADB_SEARCH_URL.format(api_key=self.TADB_API_KEY)
            params = {"s": artist_name}

            logger.debug(f"Searching TheAudioDB for artist: {artist_name}")
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("artists") and len(data["artists"]) > 0:
                artist = data["artists"][0]
                logger.info(f"Found {artist.get('strArtist')} on TheAudioDB")
                return {
                    "name": artist.get("strArtist"),
                    "thumb": artist.get("strArtistThumb"),
                    "logo": artist.get("strArtistLogo"),
                    "fanart": artist.get("strArtistFanart"),
                    "banner": artist.get("strArtistBanner"),
                }
            logger.debug(f"Artist {artist_name} not found on TheAudioDB")
            return {}  # noqa: TRY300

        except Exception:  # noqa: BLE001
            logger.exception(f"Error searching TheAudioDB for {artist_name}")
            return {}

    def download_image_content(self, url: str) -> bytes | None:
        """
        Download image content from a URL.

        Args:
            url: URL of the image to download

        Returns:
            Image bytes or None if download fails
        """
        if not url:
            return None

        try:
            logger.debug(f"Downloading image from {url}")
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Read image content into memory
            image_content = BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                image_content.write(chunk)

            image_bytes = image_content.getvalue()
            logger.debug(f"Downloaded {len(image_bytes)} bytes")

        except Exception:  # noqa: BLE001
            logger.exception(f"Failed to download image from {url}")
            return None
        else:
            return image_bytes

    def fetch_and_save_images(self, performer: "Performer") -> dict[str, bool]:
        """
        Fetch and save performer images to the Performer model.

        Args:
            performer: Performer instance to update with images

        Returns:
            Dictionary mapping image types to success status
        """
        results = {"performer_image": False, "logo_image": False}

        # Search TheAudioDB for artist data
        artist_data = self.search_theaudiodb(performer.name)

        if not artist_data:
            logger.debug(f"No image data found for {performer.name}")
            return results

        # Download and save performer image (thumb)
        if artist_data.get("thumb"):
            image_bytes = self.download_image_content(artist_data["thumb"])
            if image_bytes:
                try:
                    # Save to Django ImageField
                    filename = f"{performer.name}_image.jpg"
                    performer.performer_image.save(filename, ContentFile(image_bytes), save=False)
                    results["performer_image"] = True
                    logger.info(f"Saved performer image for {performer.name}")
                except Exception:  # noqa: BLE001
                    logger.exception(f"Failed to save performer image for {performer.name}")

        # Download and save logo image
        if artist_data.get("logo"):
            logo_bytes = self.download_image_content(artist_data["logo"])
            if logo_bytes:
                try:
                    # Determine extension from URL or default to png
                    extension = "png" if ".png" in artist_data["logo"].lower() else "jpg"
                    filename = f"{performer.name}_logo.{extension}"
                    performer.logo_image.save(filename, ContentFile(logo_bytes), save=False)
                    results["logo_image"] = True
                    logger.info(f"Saved logo image for {performer.name}")
                except Exception:  # noqa: BLE001
                    logger.exception(f"Failed to save logo image for {performer.name}")

        return results


def fetch_and_update_performer_images(performer: "Performer") -> dict[str, bool]:
    """
    Fetch and update images for a performer.

    This function is called automatically when a new Performer is created.

    Args:
        performer: Performer instance

    Returns:
        Dictionary mapping image types to success status
    """
    # Skip if performer already has both images
    if performer.performer_image and performer.logo_image:
        logger.debug(f"Performer {performer.name} already has images")
        return {"performer_image": True, "logo_image": True}

    fetcher = PerformerImageFetcher()
    results = fetcher.fetch_and_save_images(performer)

    # Save the performer if any images were added
    if any(results.values()):
        try:
            # Use update_fields to avoid triggering save hooks again
            performer.save(update_fields=["performer_image", "logo_image"])
            logger.info(f"Updated performer {performer.name} with images")
        except Exception:  # noqa: BLE001
            logger.exception(f"Failed to save performer {performer.name} after updating images")

    return results
