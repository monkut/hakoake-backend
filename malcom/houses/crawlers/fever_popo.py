import logging
import re

from django.utils import timezone

from .crawler import CrawlerRegistry, LiveHouseWebsiteCrawler

logger = logging.getLogger(__name__)

FEVER_POPO_BASE_URL = "https://www.fever-popo.com"


@CrawlerRegistry.register("FeverPopoCrawler")
class FeverPopoCrawler(LiveHouseWebsiteCrawler):
    """
    Crawler for 新代田FEVER (LIVE HOUSE FEVER) website.

    Schedule page structure:
    - <h3>YY.MM.DD (Day) Event Title</h3>
    - <p><img src="...flyer..."></p>
    - <h4>Performer1<br>Performer2<br>...</h4>
    - <p>OPEN HH:MM / START HH:MM</p>
    - <p>ADV ¥XXXX / DOOR ¥XXXX</p>
    """

    def extract_live_house_info(self, html_content: str) -> dict[str, str]:
        return {
            "name": "新代田FEVER",
            "name_kana": "シンダイタフィーバー",
            "name_romaji": "Shindaita FEVER",
            "address": "東京都世田谷区羽根木1-1-14 新代田ビル1F",
            "phone_number": "03-6304-7899",
            "capacity": 0,
            "opened_date": None,
        }

    def find_schedule_link(self, html_content: str) -> str | None:
        current_date = timezone.localdate()
        return f"{FEVER_POPO_BASE_URL}/schedule/{current_date.year}/{current_date.month:02d}/"

    def extract_performance_schedules(self, html_content: str) -> list[dict]:  # noqa: C901, PLR0912, PLR0915
        """
        Extract performance schedules from FEVER schedule page.

        Each event begins with an <h3> containing the date and event name,
        followed by an optional flyer image, an <h4> of performers, and
        <p> tags for times and ticket details.
        """
        soup = self.create_soup(html_content)
        schedules = []

        h3_elements = soup.find_all("h3")
        logger.debug(f"Found {len(h3_elements)} H3 event headers on FEVER schedule page")

        for h3 in h3_elements:
            h3_text = h3.get_text(strip=True)

            # Date format: YY.MM.DD (Day) Event Name  e.g. "26.04.01 (Wed) Event Title"
            date_match = re.match(r"(\d{2})\.(\d{2})\.(\d{2})\s*\([^)]+\)\s*(.*)", h3_text)
            if not date_match:
                continue

            yy = int(date_match.group(1))
            month = int(date_match.group(2))
            day = int(date_match.group(3))
            event_name = date_match.group(4).strip()

            year = 2000 + yy
            date_str = f"{year:04d}-{month:02d}-{day:02d}"

            performers: list[str] = []
            open_time = "18:30"
            start_time = "19:00"
            event_image_url: str | None = None
            context_parts = [h3_text]

            # Collect sibling elements until the next event's <h3>
            sibling = h3.find_next_sibling()
            while sibling and sibling.name != "h3":
                if sibling.name == "p":
                    img = sibling.find("img", src=True)
                    if img and not event_image_url:
                        event_image_url = img["src"]

                    p_text = sibling.get_text(strip=True)
                    if p_text:
                        context_parts.append(p_text)

                    time_match = re.search(
                        r"OPEN\s*(\d{1,2}:\d{2})\s*/\s*START\s*(\d{1,2}:\d{2})", p_text, re.IGNORECASE
                    )
                    if time_match:
                        open_time = time_match.group(1)
                        start_time = time_match.group(2)

                elif sibling.name == "h4":
                    # Performers listed one per line via <br> tags
                    performer_text = sibling.get_text(separator="\n", strip=True)
                    context_parts.append(performer_text)
                    for line in performer_text.split("\n"):
                        cleaned = self._clean_performer_name(line.strip())
                        if cleaned and self._is_valid_performer_name(cleaned):
                            performers.append(cleaned)

                sibling = sibling.find_next_sibling()

            if not performers and not event_name:
                continue

            schedule: dict = {
                "date": date_str,
                "open_time": open_time,
                "start_time": start_time,
                "performers": performers if performers else [event_name],
                "performance_name": event_name,
                "context": "\n".join(context_parts),
            }
            if event_image_url:
                schedule["event_image_url"] = event_image_url
            schedules.append(schedule)

        logger.info(f"Extracted {len(schedules)} schedules from FEVER website")
        return schedules

    def find_next_month_link(self, html_content: str) -> str | None:
        current_date = timezone.localdate()
        next_month = (current_date.month % 12) + 1
        next_year = current_date.year if next_month > current_date.month else current_date.year + 1
        return f"{FEVER_POPO_BASE_URL}/schedule/{next_year}/{next_month:02d}/"
