import json
from argparse import ArgumentParser
from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import QuerySet
from houses.definitions import CrawlerCollectionState
from houses.models import LiveHouse, PerformanceSchedule
from performers.models import Performer

# Time constants for readability
MONTHS_IN_YEAR = 12  # noqa: N806
SECONDS_PER_HOUR = 3600  # noqa: N806
SECONDS_PER_MINUTE = 60  # noqa: N806


class Command(BaseCommand):
    help = (
        "Show performance collection status: venue count, performance/performer totals by month, "
        "last collection time. Use --format json for compact machine-readable output."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--months",
            type=int,
            default=2,
            help="Months to show from current month (default: 2)",
        )
        parser.add_argument(
            "--detailed",
            "-d",
            action="store_true",
            help="Text mode only: show top 5 performers per month per venue",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="text=human-readable (default), json=compact structured data for parsing",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        """
        Show collection status for all venues.

        Returns total stats + per-venue breakdown with:
        - last_collected timestamp
        - collection status (success/error/pending)
        - performance/performer counts per month
        """  # noqa: C901, PLR0912, PLR0915, PLR0911
        months_to_show = options["months"]
        detailed = options["detailed"]
        output_format = options["format"]

        # Get current date
        now = datetime.now()  # noqa: DTZ001
        current_year = now.year
        current_month = now.month

        # Calculate month range
        months = []
        for i in range(months_to_show):
            month = current_month + i
            year = current_year
            if month > MONTHS_IN_YEAR:
                month -= MONTHS_IN_YEAR
                year += 1
            months.append((year, month))

        # Get all live houses ordered by name
        live_houses = LiveHouse.objects.all().order_by("name")

        if not live_houses.exists():
            if output_format == "json":
                self.stdout.write(json.dumps({"error": "No live houses found"}))
            else:
                self.stdout.write(self.style.WARNING("No live houses found."))
            return

        # Summary statistics
        total_performances = PerformanceSchedule.objects.count()
        total_performers = Performer.objects.filter(performance_schedules__isnull=False).distinct().count()

        if output_format == "json":
            self._output_json(live_houses, months, total_performances, total_performers, detailed)
        else:
            self._output_text(live_houses, months, total_performances, total_performers, detailed)

    def _output_json(
        self,
        live_houses: QuerySet[LiveHouse],
        months: list[tuple[int, int]],
        total_performances: int,
        total_performers: int,
        detailed: bool,  # noqa: ARG002
    ) -> None:
        """Output status in compact JSON format."""
        data = {
            "total": {
                "performances": total_performances,
                "performers": total_performers,
                "venues": live_houses.count(),
            },
            "venues": [],
        }

        for live_house in live_houses:
            venue_data = {
                "name": live_house.name,
                "last_collected": (
                    live_house.last_collected_datetime.isoformat() if live_house.last_collected_datetime else None
                ),
                "status": live_house.last_collection_state or "pending",
                "months": {},
            }

            for year, month in months:
                performances = PerformanceSchedule.objects.filter(
                    live_house=live_house, performance_date__year=year, performance_date__month=month
                )
                perf_count = performances.count()
                performer_count = Performer.objects.filter(performance_schedules__in=performances).distinct().count()

                month_key = f"{year}-{month:02d}"
                venue_data["months"][month_key] = {"performances": perf_count, "performers": performer_count}

            data["venues"].append(venue_data)

        self.stdout.write(json.dumps(data, indent=2))

    def _output_text(
        self,
        live_houses: QuerySet[LiveHouse],
        months: list[tuple[int, int]],
        total_performances: int,
        total_performers: int,
        detailed: bool,
    ) -> None:
        """Output status in human-readable text format."""
        # Header
        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 80}"))
        self.stdout.write(self.style.SUCCESS("PERFORMANCE COLLECTION STATUS"))
        self.stdout.write(self.style.SUCCESS(f"{'=' * 80}\n"))

        self.stdout.write(f"Total Performances: {total_performances}")
        self.stdout.write(f"Total Unique Performers: {total_performers}")
        self.stdout.write(f"Total Venues: {live_houses.count()}\n")

        # Per-venue breakdown
        for live_house in live_houses:
            self._display_venue_status(live_house, months, detailed)

        # Footer
        self.stdout.write(self.style.SUCCESS(f"{'=' * 80}\n"))

    def _display_venue_status(self, live_house: LiveHouse, months: list[tuple[int, int]], detailed: bool) -> None:  # noqa: PLR0912
        """Display status for a single venue."""
        # Header for venue
        self.stdout.write(self.style.HTTP_INFO(f"\n{live_house.name}"))
        self.stdout.write("-" * 80)

        # Collection status
        if live_house.last_collected_datetime:
            last_collected = live_house.last_collected_datetime.strftime("%Y-%m-%d %H:%M:%S")
            time_ago = self._format_time_ago(live_house.last_collected_datetime)
            self.stdout.write(f"Last Collected: {last_collected} ({time_ago})")
        else:
            self.stdout.write(self.style.WARNING("Last Collected: Never"))

        # Collection state with color coding
        state = live_house.last_collection_state or "pending"
        if state == CrawlerCollectionState.SUCCESS:
            status_display = self.style.SUCCESS(f"Status: {state}")
        elif state == CrawlerCollectionState.ERROR:
            status_display = self.style.ERROR(f"Status: {state}")
        elif state == CrawlerCollectionState.TIMEOUT:
            status_display = self.style.WARNING(f"Status: {state}")
        else:
            status_display = f"Status: {state}"
        self.stdout.write(status_display)

        # Website
        if hasattr(live_house, "website"):
            self.stdout.write(f"Website: {live_house.website.url}")

        self.stdout.write("")  # Empty line

        # Monthly breakdown
        for year, month in months:
            performances = PerformanceSchedule.objects.filter(
                live_house=live_house, performance_date__year=year, performance_date__month=month
            )

            perf_count = performances.count()
            # Count unique performers for this month at this venue
            performer_count = Performer.objects.filter(performance_schedules__in=performances).distinct().count()

            month_name = datetime(year, month, 1).strftime("%B %Y")  # noqa: DTZ001

            if perf_count > 0:
                self.stdout.write(f"  {month_name:20} {perf_count:3} performances, {performer_count:3} performers")

                # Detailed mode: show top performers
                if detailed:
                    # Get performers with their performance counts
                    performer_counts = defaultdict(int)
                    for perf in performances.prefetch_related("performers"):
                        for performer in perf.performers.all():
                            performer_counts[performer.name] += 1

                    if performer_counts:
                        self.stdout.write("    Top performers:")
                        # Sort by count descending and take top 5
                        top_performers = sorted(performer_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                        for name, count in top_performers:
                            self.stdout.write(f"      - {name} ({count} show{'s' if count != 1 else ''})")
            else:
                self.stdout.write(self.style.WARNING(f"  {month_name:20} No performances"))

    def _format_time_ago(self, dt: datetime) -> str:
        """Format datetime as 'X hours/days ago'."""
        now = datetime.now(tz=dt.tzinfo)
        delta = now - dt

        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        if delta.seconds >= SECONDS_PER_HOUR:
            hours = delta.seconds // SECONDS_PER_HOUR
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if delta.seconds >= SECONDS_PER_MINUTE:
            minutes = delta.seconds // SECONDS_PER_MINUTE
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        return "just now"
