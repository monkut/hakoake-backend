from datetime import date, datetime
from unittest.mock import Mock, patch

from django.test import TestCase
from performers.models import Performer

from ..crawlers import CrawlerRegistry, LaMamaCrawler, LoftProjectShelterCrawler
from ..definitions import WebsiteProcessingState
from ..models import LiveHouse, LiveHouseWebsite, PerformanceSchedule


class TestLiveHouseWebsiteCrawler(TestCase):
    """Test cases for LiveHouseWebsiteCrawler base functionality."""

    def setUp(self):
        """Set up test data."""
        self.website = LiveHouseWebsite.objects.create(
            url="https://test.example.com", state=WebsiteProcessingState.NOT_STARTED, crawler_class="TestCrawler"
        )

    def test_create_or_update_live_house_with_existing(self):
        """Test updating an existing LiveHouse."""
        crawler = LoftProjectShelterCrawler(self.website)

        # Create initial live house
        initial_data = {
            "name": "Test Venue",
            "name_kana": "TestKana",
            "name_romaji": "Test Venue",
            "address": "Old Address",
            "phone_number": "03-1234-5678",
            "capacity": 100,
            "opened_date": "2020-01-01",
        }
        live_house = crawler.create_or_update_live_house(initial_data)
        initial_id = live_house.id

        # Update with new data
        updated_data = {
            "name": "Test Venue Updated",
            "name_kana": "TestKana",
            "name_romaji": "Test Venue",
            "address": "New Address",
            "phone_number": "03-9876-5432",
            "capacity": 200,
            "opened_date": "2020-01-01",
        }
        updated_house = crawler.create_or_update_live_house(updated_data)

        # Verify it's the same object, just updated
        self.assertEqual(initial_id, updated_house.id)
        self.assertEqual(updated_house.address, "New Address")
        self.assertEqual(updated_house.capacity, 200)
        self.assertEqual(LiveHouse.objects.count(), 1)

    def test_create_performance_schedule_string_parsing(self):
        """Test performer string parsing logic."""
        crawler = LoftProjectShelterCrawler(self.website)
        live_house = LiveHouse.objects.create(
            website=self.website,
            name="Test Venue",
            name_kana="TestKana",
            name_romaji="Test",
            address="Tokyo",
            capacity=200,
            opened_date=date(2020, 1, 1),
        )

        # Test various delimiter formats
        test_cases = [
            ("Artist A, Artist B / Artist C", ["Artist A", "Artist B", "Artist C"]),
            ("TESTATESTBTESTC", ["Band A", "Band B", "Band C"]),
            ("Single Artist", ["Single Artist"]),
            ("  Trimmed  /  Spaces  ", ["Trimmed", "Spaces"]),
        ]

        for performers_string, expected_names in test_cases:
            data = {"date": "2024-12-01", "open_time": "18:00", "start_time": "18:30", "performers": performers_string}

            performance = crawler.create_performance_schedule(live_house, data)
            performer_names = list(performance.performers.values_list("name", flat=True))

            self.assertEqual(sorted(performer_names), sorted(expected_names))

            # Clean up for next test
            performance.delete()
            Performer.objects.all().delete()

    @patch("requests.Session.get")
    def test_process_performance_schedules_with_pagination(self, mock_get):  # noqa: ANN001
        """Test that process_performance_schedules handles pagination correctly."""
        crawler = LoftProjectShelterCrawler(self.website)
        live_house = LiveHouse.objects.create(
            website=self.website,
            name="Test Venue",
            name_kana="TestKana",
            name_romaji="Test",
            address="Tokyo",
            capacity=200,
            opened_date=date(2020, 1, 1),
        )

        # Mock current month page
        current_month_html = """
        <html><body>
            <div class="event">
                <p>12/15</p>
                <p>OPEN 18:00 / START 18:30</p>
                <p>Current Month Band</p>
            </div>
            <a href="/next">Next</a>
        </body></html>
        """

        # Mock next month page
        next_month_html = """
        <html><body>
            <div class="event">
                <p>1/10</p>
                <p>OPEN 19:00 / START 19:30</p>
                <p>Next Month Band</p>
            </div>
        </body></html>
        """

        # Set up mock responses
        mock_responses = [Mock(), Mock()]
        mock_responses[0].text = current_month_html
        mock_responses[0].raise_for_status = Mock()
        mock_responses[1].text = next_month_html
        mock_responses[1].raise_for_status = Mock()
        mock_get.side_effect = mock_responses

        # Process schedules
        crawler.process_performance_schedules("https://test.com/schedule", live_house)

        # Verify both months were processed
        schedules = PerformanceSchedule.objects.all()
        self.assertEqual(schedules.count(), 2)

        # Verify performers from both pages
        all_performers = Performer.objects.all()
        performer_names = set(all_performers.values_list("name", flat=True))
        self.assertIn("Current Month Band", performer_names)
        self.assertIn("Next Month Band", performer_names)


class TestLoftProjectShelterCrawler(TestCase):
    """Test cases for Loft Project Shelter crawler parsing logic."""

    def setUp(self):
        """Set up test data."""
        self.website = LiveHouseWebsite.objects.create(
            url="https://www.loft-prj.co.jp/schedule/shelter",
            state=WebsiteProcessingState.NOT_STARTED,
            crawler_class="LoftProjectShelterCrawler",
        )
        self.crawler = LoftProjectShelterCrawler(self.website)

    def test_extract_performance_schedules_date_parsing(self):
        """Test date parsing logic with year rollover."""
        # Mock it being December
        with patch("houses.crawlers.loft_project_shelter.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 1)  # noqa: DTZ001
            mock_datetime.strptime = datetime.strptime

            html = """
            <html><body>
                <div class="event">
                    <p>12/15</p>
                    <p>OPEN 18:00 / START 18:30</p>
                    <p>December Band</p>
                </div>
                <div class="event">
                    <p>1/5</p>
                    <p>OPEN 19:00 / START 19:30</p>
                    <p>January Band</p>
                </div>
            </body></html>
            """

            schedules = self.crawler.extract_performance_schedules(html)

            # December should be current year
            self.assertEqual(schedules[0]["date"], "2024-12-15")
            # January should be next year
            self.assertEqual(schedules[1]["date"], "2025-01-05")

    def test_extract_performance_schedules_time_format_variations(self):
        """Test various time format extractions."""
        html = """
        <html><body>
            <div class="event">
                <p>12/1</p>
                <p>OPEN 18:00 / START 18:30</p>
                <p>Band A</p>
            </div>
            <div class="event">
                <p>12/2</p>
                <p>TEST4 19:00 / TEST 19:30</p>
                <p>Band B</p>
            </div>
            <div class="event">
                <p>12/3</p>
                <p>17:30 / 18:00</p>
                <p>Band C</p>
            </div>
            <div class="event">
                <p>12/4</p>
                <p>No time info</p>
                <p>Band D</p>
            </div>
        </body></html>
        """

        schedules = self.crawler.extract_performance_schedules(html)

        # Check each format was parsed correctly
        self.assertEqual(schedules[0]["open_time"], "18:00")
        self.assertEqual(schedules[0]["start_time"], "18:30")

        self.assertEqual(schedules[1]["open_time"], "19:00")
        self.assertEqual(schedules[1]["start_time"], "19:30")

        self.assertEqual(schedules[2]["open_time"], "17:30")
        self.assertEqual(schedules[2]["start_time"], "18:00")

        # Default times when not found
        self.assertEqual(schedules[3]["open_time"], "18:00")
        self.assertEqual(schedules[3]["start_time"], "18:30")

    def test_extract_performance_schedules_performer_filtering(self):
        """Test performer name filtering logic."""
        html = """
        <html><body>
            <div class="event">
                <p>12/1</p>
                <p>OPEN 18:00 / START 18:30</p>
                <p>Real Band / PRESALE / Another Band / Y3000 / Third Band / DAY_OF</p>
            </div>
        </body></html>
        """

        schedules = self.crawler.extract_performance_schedules(html)

        # Should filter out price and ticket related text
        performers = schedules[0]["performers"]
        self.assertIn("Real Band", performers)
        self.assertIn("Another Band", performers)
        self.assertIn("Third Band", performers)
        self.assertNotIn("PRESALE", performers)
        self.assertNotIn("Y3000", performers)
        self.assertNotIn("DAY_OF", performers)


class TestLaMamaCrawler(TestCase):
    """Test cases for La Mama crawler parsing logic."""

    def setUp(self):
        """Set up test data."""
        self.website = LiveHouseWebsite.objects.create(
            url="https://www.lamama.net/", state=WebsiteProcessingState.NOT_STARTED, crawler_class="LaMamaCrawler"
        )
        self.crawler = LaMamaCrawler(self.website)

    def test_extract_performance_schedules_japanese_date_format(self):
        """Test Japanese date format parsing."""
        html = """
        <html><body>
            <article class="event">
                <h3>1225</h3>
                <p>open 18:30 start 19:00</p>
                <p>Christmas Band</p>
            </article>
            <article class="event">
                <h3>13</h3>
                <p>19:00 / 19:30</p>
                <p>New Year Band</p>
            </article>
        </body></html>
        """

        with patch("houses.crawlers.la_mama.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 20)  # noqa: DTZ001
            mock_datetime.strptime = datetime.strptime

            schedules = self.crawler.extract_performance_schedules(html)

            self.assertEqual(len(schedules), 2)
            self.assertEqual(schedules[0]["date"], "2024-12-25")
            self.assertEqual(schedules[1]["date"], "2025-01-03")  # Next year

    def test_extract_live_house_info_capacity_parsing(self):
        """Test various capacity format extractions."""
        test_cases = [
            ("Capacity: 300", 300),
            ("Capacity: 250", 250),
            ("Capacity: 180", 180),
            ("Capacity: 300", 300),
        ]

        for capacity_text, expected_capacity in test_cases:
            html = f"""
            <html><body>
                <section class="about">
                    <p>{capacity_text}</p>
                </section>
            </body></html>
            """

            info = self.crawler.extract_live_house_info(html)
            self.assertEqual(info["capacity"], expected_capacity)

    def test_extract_performance_schedules_performer_cleaning(self):
        """Test performer name cleaning logic."""
        html = """
        <html><body>
            <article class="event">
                <p>12/1</p>
                <p>19:00 / 19:30</p>
                <p>y%TESTBand A (from Tokyo) / Band B [TEST] / $* #</p>
            </article>
        </body></html>
        """

        schedules = self.crawler.extract_performance_schedules(html)
        performers = schedules[0]["performers"]

        # Should clean brackets and their contents
        self.assertIn("Band A", performers)
        self.assertIn("Band B", performers)
        self.assertIn("$* #", performers)

        # Should not include bracketed content
        self.assertNotIn("y%TESTBand A", performers)
        self.assertNotIn("Band A (from Tokyo)", performers)


class TestCrawlerRegistry(TestCase):
    """Test cases for CrawlerRegistry."""

    def setUp(self):
        """Clear registry before each test."""
        CrawlerRegistry._crawlers.clear()
        # Re-register our crawlers
        CrawlerRegistry._crawlers["LoftProjectShelterCrawler"] = LoftProjectShelterCrawler
        CrawlerRegistry._crawlers["LaMamaCrawler"] = LaMamaCrawler

    def test_run_invalid_crawler(self):
        """Test running non-existent crawler raises error with correct message."""
        website = LiveHouseWebsite.objects.create(
            url="https://test.com", state=WebsiteProcessingState.NOT_STARTED, crawler_class="NonExistentCrawler"
        )

        with self.assertRaises(ValueError) as cm:
            CrawlerRegistry.run_crawler(website)

        self.assertEqual(str(cm.exception), "No crawler found for class: NonExistentCrawler")


class TestCrawlerStateManagement(TestCase):
    """Test crawler state management during execution."""

    @patch("requests.Session.get")
    def test_crawler_atomic_transaction_on_failure(self, mock_get):  # noqa: ANN001
        """Test that state changes are rolled back on failure."""
        website = LiveHouseWebsite.objects.create(
            url="https://test.com", state=WebsiteProcessingState.NOT_STARTED, crawler_class="LoftProjectShelterCrawler"
        )

        # Make extract_live_house_info fail after state change
        crawler = LoftProjectShelterCrawler(website)

        # Mock successful page fetch
        mock_response = Mock()
        mock_response.text = "<html><title>Test</title></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock method to raise exception
        with (
            patch.object(crawler, "extract_live_house_info", side_effect=Exception("Parse error")),
            self.assertRaises(Exception),  # noqa: B017
        ):
            crawler.run()

        # State should be FAILED due to exception handling
        website.refresh_from_db()
        self.assertEqual(website.state, WebsiteProcessingState.FAILED)
