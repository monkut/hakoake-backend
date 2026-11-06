import logging
import re
from urllib.parse import urljoin

from django.utils import timezone

from .crawler import CrawlerRegistry, LiveHouseWebsiteCrawler

logger = logging.getLogger(__name__)

GRIT_BASE_URL = "https://grit-live.jp"
GRIT_EVENTS_URL = "https://grit-live.jp/events"


@CrawlerRegistry.register("GritAtShibuyaCrawler")
class GritAtShibuyaCrawler(LiveHouseWebsiteCrawler):
    """Crawler for GRIT at Shibuya (https://grit-live.jp/).

    Schedule listing: /events?date=YYYY%2FMM
    Event container:  <div class="blog-entry event-wrap row" event-date="YYYY-MM-DD">
    Performers:       <p class="act"> (slash-separated)
    Times:            <p class="time">OPEN HH:MM / START HH:MM</p>
    Image:            <div class="image-bg" style='background-image: url("...")'>
    """

    def extract_live_house_info(self, html_content: str) -> dict:
        return {
            "name": "GRIT at Shibuya",
            "name_kana": "グリット アット シブヤ",
            "name_romaji": "GRIT at Shibuya",
            "address": "東京都渋谷区道玄坂2丁目23−12 フォンティスビル B1F",
            "phone_number": "03-6416-1840",
            "capacity": 0,
            "opened_date": None,
        }

    def find_schedule_link(self, html_content: str) -> str | None:
        today = timezone.localdate()
        return f"{GRIT_EVENTS_URL}?date={today.year}%2F{today.month:02d}"

    def extract_performance_schedules(self, html_content: str) -> list[dict]:
        soup = self.create_soup(html_content)
        entries = soup.find_all("div", class_="blog-entry")
        schedules = []
        for entry in entries:
            try:
                schedule = self._parse_entry(entry)
                if schedule:
                    schedules.append(schedule)
            except Exception:  # noqa: BLE001
                logger.exception("Error parsing GRIT at Shibuya event entry")
        logger.info(f"Extracted {len(schedules)} schedules from GRIT at Shibuya")
        return schedules

    def _parse_entry(self, entry: object) -> dict | None:
        date_str = entry.get("event-date")
        if not date_str:
            return None

        title_tag = entry.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Skip hall rental placeholders
        if title == "HALL RENTAL":
            return None

        time_p = entry.find("p", class_="time")
        open_time, start_time = self._parse_times(time_p)

        # Skip entries with no real time (00:00/00:00 hall rentals that slipped through)
        if open_time == "00:00" and start_time == "00:00":
            return None

        act_p = entry.find("p", class_="act")
        performers = self._parse_performers(act_p.get_text(strip=True) if act_p else "", title)

        event_image_url = self._extract_image_url(entry)

        schedule: dict = {
            "date": date_str,
            "open_time": open_time or "18:30",
            "start_time": start_time or "19:00",
            "performers": performers,
            "performance_name": title,
        }
        if event_image_url:
            schedule["event_image_url"] = event_image_url
        return schedule

    def _parse_times(self, time_p: object) -> tuple[str | None, str | None]:
        if not time_p:
            return None, None
        time_text = time_p.get_text(separator=" ", strip=True)
        # Format: "OPEN HH:MM / START HH:MM"
        match = re.search(r"OPEN\s+(\d{1,2}:\d{2})\s*/\s*START\s+(\d{1,2}:\d{2})", time_text)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def _parse_performers(self, act_text: str, fallback_title: str) -> list[str]:
        if not act_text:
            return [fallback_title] if fallback_title else []
        performers = []
        for raw in re.split(r"\s*/\s*", act_text):
            cleaned = self._clean_performer_name(raw.strip())
            if cleaned and self._is_valid_performer_name(cleaned):
                performers.append(cleaned)
        return performers if performers else ([fallback_title] if fallback_title else [])

    def _extract_image_url(self, entry: object) -> str | None:
        img_div = entry.find("div", class_="image-bg")
        if not img_div:
            return None
        style = img_div.get("style", "")
        match = re.search(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', style)
        if match:
            return match.group(1)
        return None

    def find_next_month_link(self, html_content: str) -> str | None:
        soup = self.create_soup(html_content)
        today = timezone.localdate()
        next_month = (today.month % 12) + 1
        next_year = today.year + (1 if next_month == 1 else 0)
        target = f"{next_year}%2F{next_month:02d}"
        # Find a nav link pointing to next month
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if f"date={target}" in href or f"date={next_year}%2F{next_month}" in href:
                return urljoin(GRIT_BASE_URL, href)
        # Fall back to constructing the URL directly
        return f"{GRIT_EVENTS_URL}?date={target}"
