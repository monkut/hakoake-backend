import datetime
from unittest.mock import patch

from django.test import TestCase

from houses.crawlers import GritAtShibuyaCrawler
from houses.definitions import WebsiteProcessingState
from houses.models import LiveHouseWebsite

EVENTS_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="ja">
<head><title>GRIT at Shibuya</title></head>
<body>
<div class="blog-entry event-wrap row" event-date="2026-11-07">
  <div class="col-sm-4 col-xs-12">
    <div class="blog-img">
      <a href="/events/39661">
        <div class="image-bg" style='background-image: url("https://ems.example.com/event1.png?disposition=inline");'>
          <div class="image-in"></div>
        </div>
      </a>
    </div>
  </div>
  <div class="col-sm-8 col-xs-12 event-info">
    <div class="desc">
      <div class="flex-child-group">
        <div class="date">
          <span class="month">11 /</span>
          <span class="day">07</span>
          <span class="week">金</span>
        </div>
      </div>
      <div class="flex-child-group">
        <h2><a href="/events/39661">君と青 Birthday Event</a></h2>
      </div>
    </div>
    <div class="info">
      <p class="act">君と青</p>
      <p class="time">OPEN 18:30
        /
        START 19:00</p>
      <p><span class="ticket-price__label">ADV ¥3,000</span></p>
    </div>
  </div>
</div>

<div class="blog-entry event-wrap row" event-date="2026-11-18">
  <div class="col-sm-4 col-xs-12">
    <div class="blog-img">
      <a href="/events/40000">
        <div class="image-bg" style='background-image: url("https://ems.example.com/event2.png?disposition=inline");'>
          <div class="image-in"></div>
        </div>
      </a>
    </div>
  </div>
  <div class="col-sm-8 col-xs-12 event-info">
    <div class="desc">
      <div class="flex-child-group">
        <div class="date">
          <span class="month">11 /</span>
          <span class="day">18</span>
          <span class="week">火</span>
        </div>
      </div>
      <div class="flex-child-group">
        <h2><a href="/events/40000">INTERSECTION</a></h2>
      </div>
    </div>
    <div class="info">
      <p class="act">blend house/lo-key design/Mashoe/Shun Izutani (Re.)</p>
      <p class="time">OPEN 18:30
        /
        START 19:00</p>
    </div>
  </div>
</div>

<div class="blog-entry event-wrap row" event-date="2026-11-20">
  <div class="col-sm-4 col-xs-12">
    <div class="blog-img">
      <a href="/events/40001">
        <div class="image-bg" style='background-image: url("https://ems.example.com/event3.png");'>
          <div class="image-in"></div>
        </div>
      </a>
    </div>
  </div>
  <div class="col-sm-8 col-xs-12 event-info">
    <div class="desc">
      <div class="flex-child-group">
        <h2><a href="/events/40001">HALL RENTAL</a></h2>
      </div>
    </div>
    <div class="info">
      <p class="act"></p>
      <p class="time">OPEN 00:00
        /
        START 00:00</p>
    </div>
  </div>
</div>

<a href="/events?date=2026%2F10">2026.10</a>
<a href="/events?date=2026%2F12">2026.12</a>
<a href="/events?date=2027%2F01">2027.1</a>
</body>
</html>
"""


class TestGritAtShibuyaCrawler(TestCase):
    def setUp(self):
        self.website = LiveHouseWebsite.objects.create(
            url="https://grit-live.jp/",
            state=WebsiteProcessingState.NOT_STARTED,
            crawler_class="GritAtShibuyaCrawler",
        )
        self.crawler = GritAtShibuyaCrawler(self.website)

    def test_extract_live_house_info(self):
        info = self.crawler.extract_live_house_info("")
        self.assertEqual(info["name"], "GRIT at Shibuya")
        self.assertEqual(info["phone_number"], "03-6416-1840")
        self.assertIn("渋谷区", info["address"])

    def test_find_schedule_link(self):
        with patch("houses.crawlers.grit_at_shibuya.timezone") as mock_tz:
            mock_tz.localdate.return_value = datetime.date(2026, 11, 6)
            link = self.crawler.find_schedule_link("")
        self.assertEqual(link, "https://grit-live.jp/events?date=2026%2F11")

    def test_extract_performance_schedules_count(self):
        # Only 2 real events; HALL RENTAL is filtered
        schedules = self.crawler.extract_performance_schedules(EVENTS_PAGE_HTML)
        self.assertEqual(len(schedules), 2)

    def test_extract_performance_schedules_first_event(self):
        schedules = self.crawler.extract_performance_schedules(EVENTS_PAGE_HTML)
        first = schedules[0]
        self.assertEqual(first["date"], "2026-11-07")
        self.assertEqual(first["open_time"], "18:30")
        self.assertEqual(first["start_time"], "19:00")
        self.assertEqual(first["performance_name"], "君と青 Birthday Event")
        self.assertIn("君と青", first["performers"])
        self.assertIn("event_image_url", first)

    def test_extract_performance_schedules_multiple_performers(self):
        schedules = self.crawler.extract_performance_schedules(EVENTS_PAGE_HTML)
        second = schedules[1]
        self.assertEqual(second["date"], "2026-11-18")
        self.assertIn("blend house", second["performers"])
        self.assertIn("lo-key design", second["performers"])
        self.assertIn("Mashoe", second["performers"])

    def test_hall_rental_filtered(self):
        schedules = self.crawler.extract_performance_schedules(EVENTS_PAGE_HTML)
        titles = [s["performance_name"] for s in schedules]
        self.assertNotIn("HALL RENTAL", titles)

    def test_find_next_month_link(self):
        with patch("houses.crawlers.grit_at_shibuya.timezone") as mock_tz:
            mock_tz.localdate.return_value = datetime.date(2026, 11, 6)
            link = self.crawler.find_next_month_link(EVENTS_PAGE_HTML)
        self.assertIn("2026%2F12", link)

    def test_find_next_month_link_year_rollover(self):
        with patch("houses.crawlers.grit_at_shibuya.timezone") as mock_tz:
            mock_tz.localdate.return_value = datetime.date(2026, 12, 1)
            link = self.crawler.find_next_month_link(EVENTS_PAGE_HTML)
        self.assertIn("2027%2F01", link)
