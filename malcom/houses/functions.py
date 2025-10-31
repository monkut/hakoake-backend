import json
import logging
from datetime import datetime
from pathlib import Path

import ollama
from django.conf import settings
from django.core import management
from django.utils import timezone
from performers.models import Performer

from .crawlers import CrawlerRegistry
from .definitions import CrawlerCollectionState, WebsiteProcessingState
from .models import LiveHouse, LiveHouseWebsite, MonthlyPlaylist, PerformanceSchedule

logger = logging.getLogger(__name__)


APP_TEMPLATE_DIR = Path(__name__).parent / "templates"


def collect_schedules(venue_id: int | None = None) -> None:
    """
    Collect schedules from registered LiveHouseWebsite objects by running their associated crawlers.
    Only crawl websites that haven't been successfully collected today.

    Args:
        venue_id: Optional LiveHouse ID. If provided, only collect schedules for this venue.
    """
    today = timezone.localdate()

    # Query all LiveHouseWebsite objects that have a crawler_class defined
    # and exclude those that have been successfully collected today
    websites = LiveHouseWebsite.objects.exclude(crawler_class="").exclude(crawler_class__isnull=True)

    # If venue_id is provided, filter to only that venue's website
    if venue_id is not None:
        websites = websites.filter(live_houses__id=venue_id)

    # Filter out websites where any associated LiveHouse was successfully collected today
    websites_to_exclude = set()
    for website in websites:
        live_houses_collected_today = website.live_houses.filter(
            last_collected_datetime__date=today, last_collection_state=CrawlerCollectionState.SUCCESS
        )
        if live_houses_collected_today.exists():
            websites_to_exclude.add(website.id)

    websites = websites.exclude(id__in=websites_to_exclude)

    logger.info(f"Found {websites.count()} websites to crawl (excluding already collected today)")
    if websites_to_exclude:
        logger.info(f"Skipped {len(websites_to_exclude)} websites already successfully collected today")

    success_count = 0
    failed_count = 0
    skipped_count = len(websites_to_exclude)

    for website in websites:
        # Get live house info for this website
        live_house = website.live_houses.first()
        live_house_name = live_house.name if live_house else "Unknown Live House"

        logger.info(f"🏠 Processing Live House: {live_house_name}")
        logger.info(f"   URL: {website.url}")
        logger.info(f"   Crawler: {website.crawler_class}")

        # Get before counts for comparison
        before_schedules = PerformanceSchedule.objects.filter(live_house=live_house).count() if live_house else 0
        before_performers = Performer.objects.count()

        try:
            # Run the crawler for this website
            CrawlerRegistry.run_crawler(website)
            success_count += 1

            # Get after counts for results
            after_schedules = PerformanceSchedule.objects.filter(live_house=live_house).count() if live_house else 0
            after_performers = Performer.objects.count()

            new_schedules = after_schedules - before_schedules
            new_performers = after_performers - before_performers

            logger.info(f"✅ Successfully crawled {live_house_name}")
            logger.info(f"   📅 Performance Schedules: {new_schedules} new ({after_schedules} total)")
            logger.info(f"   🎭 Performers: {new_performers} new ({after_performers} total)")
            if live_house:
                logger.info(f"   🎪 Venue Capacity: {live_house.capacity}")
            logger.info("")  # Empty line for readability

        except Exception:  # noqa: BLE001
            failed_count += 1
            logger.exception("❌ Failed to crawl {live_house_name}: {str(e)}")  # noqa: TRY401
            logger.exception("   URL: {website.url}")
            logger.exception("")  # Empty line for readability

            # The crawler should have already set the state to FAILED
            # but ensure it's set in case of unexpected errors
            website.state = WebsiteProcessingState.FAILED
            website.save()

    logger.info(f"Crawling complete: {success_count} successful, {failed_count} failed, {skipped_count} skipped")

    # After crawling, dump the data
    dump_collected_data()


def dump_collected_data() -> str:
    """
    Dump houses and performers app data to a timestamped JSON file.
    Returns the path to the created file.
    """
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")  # noqa: DTZ001
    filename = f"collected-{timestamp}.json"

    # Create data directory if it doesn't exist
    data_dir = Path(settings.BASE_DIR) / "data"
    data_dir.mkdir(exist_ok=True)

    filepath = data_dir / filename

    logger.info(f"Dumping data to {filepath}")

    # Use Django's dumpdata command to export houses and performers apps
    with open(filepath, "w") as f:  # noqa: PTH123
        management.call_command("dumpdata", "houses", "performers", format="json", indent=2, stdout=f)

    logger.info(f"Data dumped successfully to {filepath}")

    # Also create a summary
    create_collection_summary(filepath, timestamp)

    return str(filepath)


def create_collection_summary(data_filepath: Path, timestamp: str) -> None:  # noqa: C901, PLR0912, PLR0915, PLR0911
    """Create a summary of the collected data."""
    summary = {
        "collection_timestamp": timestamp,
        "statistics": {
            "live_houses": LiveHouse.objects.count(),
            "performance_schedules": PerformanceSchedule.objects.count(),
            "performers": Performer.objects.count(),
            "websites": {
                "total": LiveHouseWebsite.objects.count(),
                "completed": LiveHouseWebsite.objects.filter(state=WebsiteProcessingState.COMPLETED).count(),
                "failed": LiveHouseWebsite.objects.filter(state=WebsiteProcessingState.FAILED).count(),
                "not_started": LiveHouseWebsite.objects.filter(state=WebsiteProcessingState.NOT_STARTED).count(),
                "in_progress": LiveHouseWebsite.objects.filter(state=WebsiteProcessingState.IN_PROGRESS).count(),
            },
        },
        "data_file": data_filepath.name,
    }

    # Save summary
    summary_path = data_filepath.parent / f"collection-summary-{timestamp}.json"
    with open(summary_path, "w") as f:  # noqa: PTH123
        json.dump(summary, f, indent=2)

    logger.info(f"Summary saved to {summary_path}")
    logger.info("Collection Summary:")
    logger.info(f"  - Live Houses: {summary['statistics']['live_houses']}")
    logger.info(f"  - Performance Schedules: {summary['statistics']['performance_schedules']}")
    logger.info(f"  - Performers: {summary['statistics']['performers']}")
    logger.info(
        f"  - Websites crawled: {summary['statistics']['websites']['completed']}/{summary['statistics']['websites']['total']}"  # noqa: E501
    )


def generate_playlist_introduction_text(playlist: MonthlyPlaylist) -> str:  # noqa: ARG001
    # TODO: read prompt, "PLAYLIST_INTRO_PROMPT.md" from the templates directory
    APP_TEMPLATE_DIR / "PLAYLIST_INTRO_PROMPT.md"
    # Unused: playlist_intro_prompt

    model = settings.MODEL
    #     # user_query  # TODO: Fix undefined variable = _prepare_# user_query  # TODO: Fix undefined variable(requirement_id, requirement_text, requirement_type)  # noqa: E501
    try:
        # Call Ollama API
        response = ollama.chat(
            model=model,
            messages=[
                #                 {"role": "system", "content": REQUIREMENTS_ASSESSOR_PROMPT},
                #                 {"role": "user", "content": user_query},  # TODO: Fix undefined variable
            ],
        )

        # Extract the feedback text from the response
        feedback = response["message"]["content"]

    except ollama.ResponseError as e:
        logger.exception("Ollama API error occurred")
        http_not_found = 404
        if e.status_code == http_not_found:
            error_msg = f"Model '{model}' not found. Please run: ollama pull hf.co/mmnga/{model}"
        else:
            error_msg = f"Ollama API error: {e.error}"
        logger.exception(error_msg)
        return f"Error evaluating requirement: {error_msg}"

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error during evaluation")
        return "Error evaluating requirement: Unexpected error occurred"
    else:
        #         logger.info(f"Evaluating {requirement_id} ({requirement_type.value}) requirement ... DONE")
        return feedback
