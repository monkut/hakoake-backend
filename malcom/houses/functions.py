import asyncio
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

import edge_tts
import numpy as np
import ollama
import qrcode
from django.conf import settings
from django.core import management
from django.db.models import Count
from django.utils import timezone
from moviepy import AudioArrayClip, AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips
from performers.models import Performer, PerformerSocialLink
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment
from pydub.generators import WhiteNoise

from .crawlers import CrawlerRegistry
from .definitions import CrawlerCollectionState, WebsiteProcessingState
from .models import LiveHouse, LiveHouseWebsite, MonthlyPlaylist, MonthlyPlaylistEntry, PerformanceSchedule

logger = logging.getLogger(__name__)


APP_TEMPLATE_DIR = Path(__file__).parent / "templates"


# Robotic voice presets for TTS
ROBOTIC_VOICE_PRESETS = {
    "military": {
        "name": "robotic_military",
        "description": "Military-style robotic voice - authoritative",
        "edge_voice": "en-US-EricNeural",
        "rate": "+5%",
        "pitch": "-15Hz",
        "static_level": -12,
        "bitrate": "56k",
        "sample_rate": 12000,
    },
    "emergency_broadcast": {
        "name": "robotic_emergency_broadcast",
        "description": "Emergency broadcast - military style with light static",
        "edge_voice": "en-US-EricNeural",
        "rate": "+0%",
        "pitch": "-22Hz",
        "static_level": -17,
        "bitrate": "64k",
        "sample_rate": 16000,
    },
}


async def generate_robotic_tts(
    text: str,
    output_path: Path,
    voice_preset: str = "emergency_broadcast",
    static_percentage: float = 5.0,
) -> None:
    """Generate TTS audio with robotic effects.

    Args:
        text: Text to convert to speech
        output_path: Path where the MP3 file will be saved
        voice_preset: Voice preset to use ("military" or "emergency_broadcast")
        static_percentage: Percentage of audio to apply static (0-100), default 5%
    """
    if voice_preset not in ROBOTIC_VOICE_PRESETS:
        msg = f"Invalid voice preset: {voice_preset}. Choose from: {list(ROBOTIC_VOICE_PRESETS.keys())}"
        raise ValueError(msg)

    preset = ROBOTIC_VOICE_PRESETS[voice_preset]

    # Generate base TTS audio using edge-tts
    logger.info(f"Generating TTS with voice: {preset['edge_voice']}")
    communicate = edge_tts.Communicate(text, preset["edge_voice"], rate=preset["rate"], pitch=preset["pitch"])
    await communicate.save(str(output_path))

    # Apply robotic effects
    logger.info(f"Applying robotic effects (static: {static_percentage:.1f}%)")

    # Load the audio
    audio = AudioSegment.from_mp3(str(output_path))

    # Convert percentage to probability (0-100 -> 0.0-1.0)
    static_probability = static_percentage / 100.0

    # Apply static intermittently
    chunk_duration_ms = 200  # 200ms chunks for static application
    chunks = []
    static_chunks_count = 0

    # Initialize random generator
    rng = np.random.default_rng()

    for chunk_start in range(0, len(audio), chunk_duration_ms):
        chunk = audio[chunk_start : chunk_start + chunk_duration_ms]

        # Random chance to add static to this chunk
        if rng.random() < static_probability:
            # Generate noise for this chunk only
            noise = WhiteNoise().to_audio_segment(duration=len(chunk))
            # Mix chunk with noise
            chunk = chunk.overlay(noise + preset["static_level"])
            static_chunks_count += 1

        chunks.append(chunk)

    robotic_audio = sum(chunks) if chunks else audio
    logger.info(f"Applied static to {static_chunks_count} chunks ({static_chunks_count * chunk_duration_ms}ms total)")

    # Apply quality reduction based on preset for more "digital" artifacts
    robotic_audio = robotic_audio.set_frame_rate(preset["sample_rate"])

    # Export with preset's bitrate for varied compression artifacts
    robotic_audio.export(str(output_path), format="mp3", bitrate=preset["bitrate"])
    logger.info(f"Robotic TTS audio saved to: {output_path}")


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


def generate_playlist_introduction_text(playlist: MonthlyPlaylist) -> tuple[str, list]:
    # TODO: read prompt, "PLAYLIST_INTRO_PROMPT.md" from the templates directory
    playlist_intro_prompt_filepath = APP_TEMPLATE_DIR / "PLAYLIST_INTRO_PROMPT.md"
    assert playlist_intro_prompt_filepath.exists(), f"not found: {playlist_intro_prompt_filepath.resolve()}"
    playlist_intro_prompt = playlist_intro_prompt_filepath.read_text(encoding="utf8")

    messages = [
        {"role": "system", "content": playlist_intro_prompt},
    ]

    # Get the number of MonthlyPlaylistEntry items for each performer in other playlists
    # Returns dict: {performer_id: count, ...}
    performer_playlist_appearances = dict(
        MonthlyPlaylistEntry.objects.exclude(playlist=playlist)
        .values("song__performer")
        .annotate(count=Count("id"))
        .values_list("song__performer", "count")
    )

    # prepare playlist data:
    user_query = [
        f"For the month of {playlist.date.strftime('%B')} write an introduction to selected artists below, describing where and when they will play."  # noqa: E501
        "The site's description is as follows (DO NOT INCLUDE it in the result response, but consider it for flavor):\n"
        "Forget the stadiums. The best music is found in dark cramped basement bars, or as the call them in Japan, 'Live Houses'."  # noqa: E501
        "Explore the current Tokyo 'Live House' scene with us, as we spotlight lesser known bands playing the city's most intimate venues."  # noqa: E501
        "We only share music from artists playing at venues with a capacity of 350 or less.\n\n"
        "Selected Artists/Performers (appear in the order they appear in the playlist):\n"
    ]
    # Calculate month boundaries for filtering performances
    month_start = playlist.date
    if playlist.date.month == 12:  # noqa: PLR2004
        month_end = playlist.date.replace(year=playlist.date.year + 1, month=1, day=1)
    else:
        month_end = playlist.date.replace(month=playlist.date.month + 1, day=1)

    playlist_entry_data = []
    for entry in playlist.monthlyplaylistentry_set.order_by("position"):
        entry_data = [
            f"{entry.position}. Artist: {entry.song.performer.name}\n",
            f"\t- name kana: {entry.song.performer.name_kana}\n",
            f"\t- name romaji: {entry.song.performer.name_romaji}\n",
            f"\t- website: {entry.song.performer.website}\n",
            f"\t- email: {entry.song.performer.email}\n",
            f"\t- song (youtube link title): {entry.song.title}\n",
            f"\t- youtube release date: {entry.song.release_date}\n",
            f"\t- playlist appearances: {performer_playlist_appearances.get(entry.song.performer.id, 0)}\n",
        ]
        if entry.song.performer.name_romaji:
            entry_data.append(
                f"\t- email: {entry.song.performer.name_romaji}\n",
            )

        for social in PerformerSocialLink.objects.filter(performer=entry.song.performer):
            entry_data.append(f"\t- {social.platform}: {social.url}\n")

        # Add performance schedule details for this month
        performances = (
            PerformanceSchedule.objects.filter(
                performers=entry.song.performer,
                performance_date__gte=month_start,
                performance_date__lt=month_end,
            )
            .select_related("live_house")
            .order_by("performance_date")
        )

        if performances.exists():
            entry_data.append(f"\t- performances in {playlist.date.strftime('%B %Y')}:\n")
            for perf in performances:
                entry_data.append(f"\t\t- date: {perf.performance_date.strftime('%Y-%m-%d (%a)')}\n")
                entry_data.append(f"\t\t  venue: {perf.live_house.name}\n")
                entry_data.append(f"\t\t  venue kana: {perf.live_house.name_kana}\n")
                entry_data.append(f"\t\t  venue romaji: {perf.live_house.name_romaji}\n")
                entry_data.append(f"\t\t  open: {perf.open_time.strftime('%H:%M') if perf.open_time else 'TBA'}\n")
                entry_data.append(f"\t\t  start: {perf.start_time.strftime('%H:%M') if perf.start_time else 'TBA'}\n")

        entry_data.append("\n")

        playlist_entry_data.extend(entry_data)
    user_query.extend(playlist_entry_data)
    messages.append({"role": "user", "content": "".join(user_query)})

    try:
        # Call Ollama API
        response = ollama.chat(model=settings.PLAYLIST_INTRO_TEXT_GENERATION_MODEL, messages=messages)
        # Extract the feedback text from the response
        result_introduction = response["message"]["content"]

    except ollama.ResponseError as e:
        logger.exception("Ollama API error occurred")
        http_not_found = 404
        if e.status_code == http_not_found:
            error_msg = (
                f"Model '{settings.PLAYLIST_INTRO_TEXT_GENERATION_MODEL}' not found. "
                f"Please run: ollama pull hf.co/mmnga/{settings.PLAYLIST_INTRO_TEXT_GENERATION_MODEL}"
            )
        else:
            error_msg = f"Ollama API error: {e.error}"
        logger.exception(error_msg)
        raise

    return result_introduction, playlist_entry_data


def generate_playlist_video(playlist: MonthlyPlaylist) -> Path:  # noqa: C901, PLR0915, PLR0912
    """Generate a video for the monthly playlist with QR codes, slides, and TTS narration."""
    # Generate introduction text
    result_introduction, playlist_entry_data = generate_playlist_introduction_text(playlist)

    # Create temp directory for assets
    temp_dir = Path(tempfile.mkdtemp())
    logger.info(f"Created temp directory: {temp_dir}")

    # Video settings
    video_width = 1920
    video_height = 1080
    slide_duration = 8  # seconds per slide
    bg_color = (20, 20, 30)  # Dark blue background
    text_color = (255, 255, 255)  # White text

    slides = []

    # Helper function to create QR code
    def create_qr_code(url: str, size: int = 200) -> Image.Image:
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").resize((size, size))

    # Helper function to create slide
    def create_slide(
        title: str,
        subtitle: str = "",
        description: str = "",
        qr_urls: list[str] | None = None,
    ) -> Image.Image:
        img = Image.new("RGB", (video_width, video_height), bg_color)
        draw = ImageDraw.Draw(img)

        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
            subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
            description_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        except OSError:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            description_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Draw title
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (video_width - title_width) // 2
        draw.text((title_x, 200), title, fill=text_color, font=title_font)

        # Draw subtitle
        if subtitle:
            subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_x = (video_width - subtitle_width) // 2
            draw.text((subtitle_x, 350), subtitle, fill=text_color, font=subtitle_font)

        # Draw description
        if description:
            description_bbox = draw.textbbox((0, 0), description, font=description_font)
            description_width = description_bbox[2] - description_bbox[0]
            description_x = (video_width - description_width) // 2
            draw.text((description_x, 450), description, fill=text_color, font=description_font)

        # Draw QR codes
        if qr_urls:
            qr_size = 200
            qr_y = 550
            total_qr_width = len(qr_urls) * qr_size + (len(qr_urls) - 1) * 50
            qr_x_start = (video_width - total_qr_width) // 2

            for i, url in enumerate(qr_urls):
                qr_img = create_qr_code(url, qr_size)
                qr_x = qr_x_start + i * (qr_size + 50)
                img.paste(qr_img, (qr_x, qr_y))

                # Add label below QR code
                label = "Artist" if i == 0 else "Venue"
                label_bbox = draw.textbbox((0, 0), label, font=small_font)
                label_width = label_bbox[2] - label_bbox[0]
                label_x = qr_x + (qr_size - label_width) // 2
                draw.text((label_x, qr_y + qr_size + 10), label, fill=text_color, font=small_font)

        return img

    # 1. Create intro slide
    logger.info("Creating intro slide...")
    intro_slide = create_slide(
        title=f"HAKOAKE - {playlist.date.strftime('%B %Y')}",
        subtitle="Tokyo Live House Music Scene",
    )
    intro_path = temp_dir / "slide_intro.png"
    intro_slide.save(intro_path)
    slides.append(intro_path)

    # 2. Create slides for each performer
    logger.info(f"Creating {playlist.monthlyplaylistentry_set.count()} performer slides...")
    for entry in playlist.monthlyplaylistentry_set.order_by("position"):
        performer = entry.song.performer

        # Get first performance for this month
        month_start = playlist.date
        if playlist.date.month == 12:  # noqa: PLR2004
            month_end = playlist.date.replace(year=playlist.date.year + 1, month=1, day=1)
        else:
            month_end = playlist.date.replace(month=playlist.date.month + 1, day=1)

        performance = (
            PerformanceSchedule.objects.filter(
                performers=performer,
                performance_date__gte=month_start,
                performance_date__lt=month_end,
            )
            .select_related("live_house", "live_house__website")
            .first()
        )

        # Prepare QR codes
        qr_urls = []
        if performer.website:
            qr_urls.append(performer.website)
        if performance and hasattr(performance.live_house, "website"):
            qr_urls.append(performance.live_house.website.url)

        # Create subtitle with performance info
        subtitle = performer.name
        if performance:
            perf_date = performance.performance_date.strftime("%B %d")
            subtitle = f"{performer.name}\n{perf_date} @ {performance.live_house.name}"

        # Use song title as description
        description = f'"{entry.song.title}"' if entry.song.title else ""

        performer_slide = create_slide(
            title=f"#{entry.position}",
            subtitle=subtitle,
            description=description,
            qr_urls=qr_urls if qr_urls else None,
        )
        performer_path = temp_dir / f"slide_performer_{entry.position:02d}.png"
        performer_slide.save(performer_path)
        slides.append(performer_path)

    # 3. Create closing slide
    logger.info("Creating closing slide...")
    closing_slide = create_slide(
        title="See You Next Month!",
        subtitle="Follow @HAKOAKE for more Live House music",
    )
    closing_path = temp_dir / "slide_closing.png"
    closing_slide.save(closing_path)
    slides.append(closing_path)

    # Generate TTS using Orpheus model
    logger.info(f"Generating TTS with Orpheus model: {settings.VIDEO_TTS_MODEL}")
    audio_path = temp_dir / "narration.mp3"
    tokens_path = temp_dir / "orpheus_tokens.txt"

    try:
        # Generate TTS tokens using Orpheus
        prompt = f"<|{settings.VIDEO_TTS_VOICE}|>{result_introduction}<|eot_id|>"
        response = ollama.generate(
            model=settings.VIDEO_TTS_MODEL,
            prompt=prompt,
            options={
                "temperature": settings.VIDEO_TTS_TEMPERATURE,
                "top_p": settings.VIDEO_TTS_TOP_P,
                "repetition_penalty": settings.VIDEO_TTS_REPETITION_PENALTY,
                "num_predict": 2048,
            },
        )

        # Save Orpheus tokens for reference
        with tokens_path.open("w") as f:
            if isinstance(response, dict) and "response" in response:
                f.write(response["response"])
            else:
                f.write(str(response))

        logger.info(f"Orpheus TTS tokens generated and saved to: {tokens_path}")
        logger.info("Note: Orpheus tokens saved. Use gguf_orpheus.py or Orpheus-FastAPI to convert to audio.")

    except Exception:  # noqa: BLE001
        logger.exception("Orpheus TTS generation failed, will use edge-tts fallback")

    # Generate actual audio using edge-tts as Orpheus requires external decoder
    logger.info(f"Generating audio with edge-tts ({settings.EDGE_TTS_VOICE})...")

    async def generate_tts_audio(text: str, output_path: Path) -> None:
        """Generate TTS audio using edge-tts."""
        communicate = edge_tts.Communicate(text, settings.EDGE_TTS_VOICE)
        await communicate.save(str(output_path))

    try:
        # Run async TTS generation
        asyncio.run(generate_tts_audio(result_introduction, audio_path))
        logger.info(f"Audio generated successfully: {audio_path}")

    except Exception:  # noqa: BLE001
        logger.exception("edge-tts failed, using silent audio")
        # Create silent audio as fallback
        sample_rate = 44100
        duration = len(slides) * slide_duration
        silent_audio = np.zeros((int(duration * sample_rate), 2))
        audio_clip = AudioArrayClip(silent_audio, fps=sample_rate)
        audio_clip.write_audiofile(str(audio_path), codec="mp3")

    # Create video from slides
    logger.info("Creating video from slides...")
    video_clips = []
    for slide_path in slides:
        clip = ImageClip(str(slide_path)).with_duration(slide_duration)
        video_clips.append(clip)

    # Concatenate all slides
    final_video = concatenate_videoclips(video_clips, method="compose")

    # Add audio if available
    try:
        audio = AudioFileClip(str(audio_path))
        # Trim or loop audio to match video duration
        if audio.duration > final_video.duration:
            audio = audio.subclipped(0, final_video.duration)
        elif audio.duration < final_video.duration:
            # Loop audio to match video duration
            loops_needed = int(final_video.duration / audio.duration) + 1
            audio = concatenate_audioclips([audio] * loops_needed).subclipped(0, final_video.duration)

        final_video = final_video.with_audio(audio)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to add audio to video")

    # Save final video
    video_dir = Path(settings.BASE_DIR) / "data" / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    timestamp = playlist.date.strftime("%Y%m")
    video_filename = f"playlist_intro_{timestamp}.mp4"
    video_filepath = video_dir / video_filename

    logger.info(f"Rendering final video to {video_filepath}...")
    final_video.write_videofile(
        str(video_filepath),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=str(temp_dir / "temp_audio.m4a"),
        remove_temp=True,
    )

    logger.info(f"Video generation complete: {video_filepath}")
    return video_filepath
