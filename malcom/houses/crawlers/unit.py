import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from .crawler import CrawlerRegistry, LiveHouseWebsiteCrawler

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@CrawlerRegistry.register("UnitCrawler")
class UnitCrawler(LiveHouseWebsiteCrawler):
    """Crawler for Daikanyama UNIT (https://www.unit-tokyo.com/)."""

    SCHEDULE_BASE = "https://www.unit-tokyo.com/schedule/"

    def extract_live_house_info(self, html_content: str) -> dict:
        return {
            "name": "Daikanyama UNIT",
            "name_kana": "ダイカンヤマ ユニット",
            "name_romaji": "Daikanyama UNIT",
            "address": "",
            "phone_number": "",
            "capacity": 0,
            "opened_date": None,
        }

    def find_schedule_link(self, html_content: str) -> str:
        return self.SCHEDULE_BASE

    def find_next_month_link(self, html_content: str) -> str | None:
        soup = self.create_soup(html_content)
        nav_next = soup.find(class_="p-schedule__nav-next")
        if nav_next:
            a = nav_next.find("a", href=True)
            if a:
                return a["href"]
        return None

    def extract_performance_schedules(self, html_content: str) -> list[dict]:
        soup = self.create_soup(html_content)
        year = self._extract_year(html_content)
        schedules = []

        for item in soup.find_all(class_="p-schedule__item"):
            schedule = self._parse_item(item, year)
            if schedule:
                schedules.append(schedule)

        logger.info(f"Extracted {len(schedules)} schedules from UNIT website")
        return schedules

    def _extract_year(self, html_content: str) -> int:
        m = re.search(r'"startDate"\s*:\s*"(\d{4})-', html_content)
        if m:
            return int(m.group(1))
        return datetime.now().year  # noqa: DTZ001

    def _parse_item(self, item: "BeautifulSoup", year: int) -> dict | None:
        date_p = item.find(class_="p-schedule__item-date")
        if not date_p:
            return None
        m = re.match(r"(\d{1,2})/(\d{1,2})", date_p.get_text(strip=True))
        if not m:
            return None
        month, day = int(m.group(1)), int(m.group(2))

        open_time = None
        open_p = item.find(class_="p-schedule__item-open")
        if open_p:
            span = open_p.find("span")
            if span:
                open_time = span.get_text(strip=True)

        performers = []
        lineup_p = item.find(class_="p-schedule__item-lineup")
        if lineup_p:
            lineup_text = lineup_p.get_text(strip=True)
            performers = [p.strip() for p in re.split(r"[/／]", lineup_text) if p.strip()]
        if not performers:
            title_top = item.find(class_="p-schedule__item-title-top")
            if title_top:
                name = title_top.get_text(strip=True)
                if name:
                    performers = [name]
        if not performers:
            return None

        title_tag = item.find("h2", class_="p-schedule__item-title")
        title = title_tag.get_text(strip=True) if title_tag else None

        return {
            "date": f"{year}-{month:02d}-{day:02d}",
            "open_time": open_time,
            "start_time": open_time,
            "performers": performers[:8],
            "performance_name": title,
        }
