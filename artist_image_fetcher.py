#!/usr/bin/env python3
"""
Artist Image Fetcher - CLI tool to search and download artist images and logos.

Searches multiple sources for artist images including TheAudioDB, MusicBrainz,
and web search as fallback. Supports UTF-8 artist names including Japanese characters.
"""
# ruff: noqa: T201

import argparse
import sys
from pathlib import Path
from typing import Any

import requests


class ArtistImageFetcher:
    """Fetches artist images and logos from various online sources."""

    # TheAudioDB API (free tier)
    TADB_API_KEY = "2"  # Public test key
    TADB_SEARCH_URL = "https://www.theaudiodb.com/api/v1/json/{api_key}/search.php"

    # MusicBrainz API
    MB_SEARCH_URL = "https://musicbrainz.org/ws/2/artist/"
    MB_HEADERS = {"User-Agent": "ArtistImageFetcher/1.0"}

    def __init__(self, output_dir: Path | None = None) -> None:
        """
        Initialize the fetcher.

        Args:
            output_dir: Directory to save images. Defaults to current directory.
        """
        self.output_dir = output_dir or Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ArtistImageFetcher/1.0"})

    def search_theaudiodb(self, artist_name: str) -> dict[str, Any] | None:
        """
        Search TheAudioDB for artist information.

        Args:
            artist_name: Name of the artist to search for

        Returns:
            Dictionary with artist info including image URLs, or None if not found
        """
        try:
            url = self.TADB_SEARCH_URL.format(api_key=self.TADB_API_KEY)
            params = {"s": artist_name}

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("artists") and len(data["artists"]) > 0:
                artist = data["artists"][0]
                return {
                    "name": artist.get("strArtist"),
                    "thumb": artist.get("strArtistThumb"),
                    "logo": artist.get("strArtistLogo"),
                    "fanart": artist.get("strArtistFanart"),
                    "banner": artist.get("strArtistBanner"),
                    "source": "TheAudioDB",
                }
        except requests.RequestException as e:
            print(f"Error searching TheAudioDB: {e}", file=sys.stderr)

        return None

    def search_musicbrainz(self, artist_name: str) -> dict[str, Any] | None:
        """
        Search MusicBrainz for artist information.

        Args:
            artist_name: Name of the artist to search for

        Returns:
            Dictionary with artist info including MBID, or None if not found
        """
        try:
            params = {"query": f'artist:"{artist_name}"', "fmt": "json", "limit": 1}

            response = self.session.get(self.MB_SEARCH_URL, params=params, headers=self.MB_HEADERS, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("artists") and len(data["artists"]) > 0:
                artist = data["artists"][0]
                return {
                    "name": artist.get("name"),
                    "mbid": artist.get("id"),
                    "score": artist.get("score"),
                    "source": "MusicBrainz",
                }
        except requests.RequestException as e:
            print(f"Error searching MusicBrainz: {e}", file=sys.stderr)

        return None

    def download_image(self, url: str, filename: str) -> bool:
        """
        Download an image from a URL.

        Args:
            url: URL of the image to download
            filename: Filename to save the image as

        Returns:
            True if successful, False otherwise
        """
        if not url:
            return False

        try:
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()

            output_path = self.output_dir / filename

            with output_path.open("wb") as f:
                f.writelines(response.iter_content(chunk_size=8192))

            print(f"✓ Downloaded: {filename} ({output_path})")
        except requests.RequestException as e:
            print(f"✗ Failed to download {filename}: {e}", file=sys.stderr)
            return False
        except OSError as e:
            print(f"✗ Failed to save {filename}: {e}", file=sys.stderr)
            return False

        return True

    def fetch_artist_images(self, artist_name: str) -> dict[str, bool]:
        """
        Fetch all available images for an artist.

        Args:
            artist_name: Name of the artist

        Returns:
            Dictionary mapping image types to success status
        """
        results = {"thumb": False, "logo": False, "fanart": False, "banner": False}

        print(f"\nSearching for artist: {artist_name}")
        print("=" * 60)

        # Try TheAudioDB first
        print("Searching TheAudioDB...")
        tadb_data = self.search_theaudiodb(artist_name)

        if tadb_data:
            print(f"✓ Found on TheAudioDB: {tadb_data['name']}")

            # Download thumbnail (artist.jpg)
            if tadb_data.get("thumb"):
                results["thumb"] = self.download_image(tadb_data["thumb"], "artist.jpg")

            # Download logo
            if tadb_data.get("logo"):
                results["logo"] = self.download_image(tadb_data["logo"], "logo.png")

            # Download fanart
            if tadb_data.get("fanart"):
                results["fanart"] = self.download_image(tadb_data["fanart"], "fanart.jpg")

            # Download banner
            if tadb_data.get("banner"):
                results["banner"] = self.download_image(tadb_data["banner"], "banner.jpg")
        else:
            print("✗ Not found on TheAudioDB")

            # Try MusicBrainz as fallback for reference
            print("Searching MusicBrainz...")
            mb_data = self.search_musicbrainz(artist_name)

            if mb_data:
                print(f"✓ Found on MusicBrainz: {mb_data['name']} (score: {mb_data['score']})")
                print(f"  MBID: {mb_data['mbid']}")
                print("  Note: MusicBrainz doesn't provide direct image links")
            else:
                print("✗ Not found on MusicBrainz")

        print("=" * 60)
        return results


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Fetch artist images and logos from online sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --artist "RIS-707"
  %(prog)s --artist "CARAMEL CANDiD" --output /path/to/artist/folder
  %(prog)s --artist "赤くらげ"
        """,
    )

    parser.add_argument(
        "--artist", type=str, required=True, help="Artist name (supports UTF-8 including Japanese characters)"
    )

    parser.add_argument(
        "--output", type=Path, default=None, help="Output directory for images (default: current directory)"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Create fetcher instance
    fetcher = ArtistImageFetcher(output_dir=args.output)

    # Fetch images
    results = fetcher.fetch_artist_images(args.artist)

    # Print summary
    print("\nSummary:")
    downloaded_count = sum(1 for success in results.values() if success)
    print(f"Downloaded {downloaded_count}/{len(results)} images")

    if downloaded_count == 0:
        print("\n⚠ No images found for this artist.")
        print("Consider searching manually or adding custom images.")
        sys.exit(1)
    else:
        print(f"\n✓ Images saved to: {fetcher.output_dir}")
        sys.exit(0)


if __name__ == "__main__":
    main()
