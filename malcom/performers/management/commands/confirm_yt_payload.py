"""
Diagnostic command: fetch a real YouTube search page and print the raw duration-related
fields from ytInitialData for each video result.

Purpose: confirm what YouTube actually sends in lengthText, thumbnailOverlays, and
badges for both regular videos and live streams, so the parser can be verified against
real payloads.

Usage:
    uv run python manage.py confirm_yt_payload
    uv run python manage.py confirm_yt_payload --query "live concert japan"
    uv run python manage.py confirm_yt_payload --raw   # also dump full videoRenderer JSON
"""

import json
import re

import requests
from django.core.management.base import BaseCommand, CommandParser

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={query}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)


class Command(BaseCommand):
    help = "Fetch a real YouTube search page and print duration-related payload fields for diagnosis"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--query",
            default="live concert japan",
            help="YouTube search query (default: 'live concert japan' to surface live results)",
        )
        parser.add_argument(
            "--raw",
            action="store_true",
            help="Also dump the full videoRenderer JSON for each result",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN002, ANN003
        query = options["query"]
        show_raw = options["raw"]

        self.stdout.write(f"\nFetching YouTube search results for: {query!r}\n")

        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        url = YOUTUBE_SEARCH_URL.format(query=query.replace(" ", "+"))
        response = session.get(url, timeout=15)

        if response.status_code != 200:  # noqa: PLR2004
            self.stdout.write(self.style.ERROR(f"Request failed: HTTP {response.status_code}"))
            return

        match = re.search(r"var ytInitialData = ({.*?});</script>", response.text)
        if not match:
            self.stdout.write(self.style.ERROR("ytInitialData not found in response HTML"))
            return

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            self.stdout.write(self.style.ERROR(f"Failed to parse ytInitialData JSON: {exc}"))
            return

        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        video_count = 0
        for section in contents:
            for item in section.get("itemSectionRenderer", {}).get("contents", []):
                if "videoRenderer" not in item:
                    continue

                video = item["videoRenderer"]
                video_count += 1
                video_id = video.get("videoId", "UNKNOWN")
                title_runs = video.get("title", {}).get("runs", [])
                title = title_runs[0].get("text", "") if title_runs else ""

                length_text = video.get("lengthText")
                overlays = video.get("thumbnailOverlays", [])
                badges = video.get("badges", [])

                # Summarise overlay styles
                overlay_styles = [
                    o.get("thumbnailOverlayTimeStatusRenderer", {}).get("style", "")
                    for o in overlays
                    if "thumbnailOverlayTimeStatusRenderer" in o
                ]

                # Summarise badge styles
                badge_styles = [
                    b.get("metadataBadgeRenderer", {}).get("style", "") for b in badges if "metadataBadgeRenderer" in b
                ]

                self.stdout.write(self.style.SUCCESS(f"\n{'─' * 60}"))
                self.stdout.write(f"  #{video_count}  id={video_id!r}")
                self.stdout.write(f"  title={title!r}")
                self.stdout.write(f"  lengthText={json.dumps(length_text)}")
                self.stdout.write(f"  overlay styles={overlay_styles}")
                self.stdout.write(f"  badge styles={badge_styles}")

                if show_raw:
                    self.stdout.write("\n  --- full videoRenderer ---")
                    self.stdout.write(json.dumps(video, ensure_ascii=False, indent=2))

        if video_count == 0:
            self.stdout.write(self.style.WARNING("No videoRenderer entries found in response."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{'═' * 60}"))
            self.stdout.write(f"Total video entries found: {video_count}")
