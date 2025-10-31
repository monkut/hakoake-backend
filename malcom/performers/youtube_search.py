import logging
import re
from datetime import timedelta
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from .models import Performer, PerformerSong

logger = logging.getLogger(__name__)


class YouTubeSearcher:
    """Search YouTube for performer videos without requiring API key."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            }
        )

    def search_most_popular_videos(
        self, performer_name: str, min_duration_seconds: int = 30, max_results: int = 3
    ) -> list[dict]:
        """
        Search for the most popular videos by a performer over the minimum duration.

        Args:
            performer_name: Name of the performer to search for
            min_duration_seconds: Minimum video duration in seconds (default 30)
            max_results: Maximum number of videos to return (default 3)

        Returns:
            List of dicts with video info, sorted by popularity (most popular first)
        """
        try:
            logger.debug(f"Searching YouTube for performer: {performer_name}")

            # Create search query
            search_query = f"{performer_name} music video live concert"
            search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"

            response = self.session.get(search_url, timeout=10)
            if response.status_code != requests.codes.ok:
                logger.warning(f"YouTube search failed with status {response.status_code}")
                return []

            # Parse the response to find video data
            video_data = self._extract_video_data_from_html(response.text)

            if not video_data:
                logger.debug(f"No video data found for {performer_name}")
                return []

            # Filter videos by duration and find most popular
            suitable_videos = []
            for video in video_data:
                if video.get("duration_seconds", 0) >= min_duration_seconds:
                    suitable_videos.append(video)

            if not suitable_videos:
                logger.debug(f"No videos found over {min_duration_seconds} seconds for {performer_name}")
                return []

            # Sort by view count (descending) and take the top N most popular
            suitable_videos.sort(key=lambda x: x.get("view_count", 0), reverse=True)
            top_videos = suitable_videos[:max_results]

            logger.info(f"Found {len(top_videos)} popular videos for {performer_name}")
            for i, video in enumerate(top_videos):
                logger.debug(f"  #{i + 1}: {video['title']} ({video['view_count']} views)")

        except Exception:  # noqa: BLE001
            logger.exception(f"Error searching YouTube for {performer_name}")
            return []
        else:
            return top_videos

    def _extract_video_data_from_html(self, html_content: str) -> list[dict]:  # noqa: C901, PLR0912, PLR0915, PLR0911
        """
        Extract video data from YouTube search results HTML.

        This is a simplified implementation that looks for common patterns.
        In a production environment, you might want to use the official YouTube API.
        """
        videos = []

        try:
            # Look for JSON data in the HTML that contains video information
            # YouTube embeds data in various script tags

            # Simple regex patterns to find video IDs and basic info
            video_id_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
            title_pattern = r'"title":{"runs":\[{"text":"([^"]+)"'
            view_count_pattern = r'"viewCountText":{"simpleText":"([0-9,]+) views"'
            duration_pattern = (
                r'"lengthText":{"accessibility":{"accessibilityData":{"label":"([^"]+)"}},"simpleText":"([^"]+)"'
            )

            video_ids = re.findall(video_id_pattern, html_content)
            titles = re.findall(title_pattern, html_content)
            view_counts = re.findall(view_count_pattern, html_content)
            durations = re.findall(duration_pattern, html_content)

            # Try to match up the data (this is approximate)
            for i, video_id in enumerate(video_ids[:10]):  # Limit to first 10 results
                video_data = {
                    "video_id": video_id,
                    "title": titles[i] if i < len(titles) else f"Video {i + 1}",
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "view_count": self._parse_view_count(view_counts[i] if i < len(view_counts) else "0"),
                    "duration_seconds": self._parse_duration(durations[i][1] if i < len(durations) else "0:30"),
                }
                videos.append(video_data)

            # If regex approach didn't work well, return empty list
            if not videos:
                logger.debug("No videos found from parsing HTML")

        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error parsing YouTube HTML: {e!s}")

        return videos

    def _parse_view_count(self, view_text: str) -> int:  # noqa: C901, PLR0912, PLR0915, PLR0911
        """Parse view count text like '1,234,567 views' to integer."""
        try:
            # Remove commas and 'views' text, then convert to int
            clean_text = re.sub(r"[^\d]", "", view_text)
            return int(clean_text) if clean_text else 0
        except (ValueError, AttributeError):
            return 0

    def _parse_duration(self, duration_text: str) -> int:  # noqa: C901, PLR0912, PLR0915, PLR0911
        """Parse duration text like '3:45' to seconds."""
        try:
            if ":" in duration_text:
                parts = duration_text.split(":")
                if len(parts) == 2:  # noqa: PLR2004  # MM:SS
                    minutes, seconds = int(parts[0]), int(parts[1])
                    return minutes * 60 + seconds
                if len(parts) == 3:  # noqa: PLR2004  # HH:MM:SS
                    hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
            return int(float(duration_text))  # If it's just a number
        except (ValueError, AttributeError):
            return 30  # Default to 30 seconds if parsing fails


def search_and_create_performer_songs(performer: "Performer") -> list["PerformerSong"]:
    """
    Search for the top 3 most popular YouTube videos for the performer and create PerformerSong instances.

    Args:
        performer: Performer instance

    Returns:
        List of created PerformerSong instances
    """
    from .models import PerformerSong  # noqa: PLC0415  # Import here to avoid circular imports

    # Check if performer already has songs to avoid duplicates
    if performer.songs.filter(youtube_video_id__isnull=False).exclude(youtube_video_id="").exists():
        logger.debug(f"Performer {performer.name} already has YouTube songs")
        return []

    searcher = YouTubeSearcher()
    videos_data = searcher.search_most_popular_videos(performer.name, min_duration_seconds=30, max_results=3)

    if not videos_data:
        logger.debug(f"No suitable YouTube videos found for {performer.name}")
        return []

    created_songs = []
    for video_data in videos_data:
        try:
            # Create PerformerSong instance
            song = PerformerSong.objects.create(
                performer=performer,
                title=video_data["title"],
                duration=timedelta(seconds=video_data["duration_seconds"]),
                youtube_video_id=video_data["video_id"],
                youtube_url=video_data["youtube_url"],
                youtube_view_count=video_data["view_count"],
                youtube_duration_seconds=video_data["duration_seconds"],
            )

            logger.info(f"Created song for {performer.name}: {song.title}")
            created_songs.append(song)

        except Exception:  # noqa: BLE001
            logger.exception(f"Failed to create PerformerSong for {performer.name}")
            continue

    return created_songs
