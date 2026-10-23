"""Common utility functions shared across the project."""

import datetime
import logging
import mimetypes
from collections.abc import Callable, Sequence
from http import HTTPStatus

import requests

YYYY_MM_LENGTH = 7
YYYY_MM_DD_LENGTH = 10

LITTERBOX_API_URL = "https://litterbox.catbox.moe/resources/internals/api.php"
LITTERBOX_TTL = "1h"
UGUU_API_URL = "https://uguu.se/upload"
UPLOAD_TIMEOUT_SECONDS = 60

logger = logging.getLogger(__name__)


class ImageHostUploadError(RuntimeError):
    """Raised when a public image-host upload fails (any provider)."""


class LitterboxUploadError(ImageHostUploadError):
    """Raised when a litterbox.catbox.moe upload fails."""


class UguuUploadError(ImageHostUploadError):
    """Raised when a uguu.se upload fails."""


def upload_to_litterbox(image_bytes: bytes, filename: str = "image.jpg") -> str:
    """Upload bytes to litterbox.catbox.moe anonymously and return the public HTTPS URL.

    litterbox.catbox.moe is catbox.moe's temporary-file sibling service. Files expire
    after ``LITTERBOX_TTL`` (currently ``1h``) — ample for Instagram carousel container
    creation, which completes in seconds. Accepts a multipart POST with
    ``reqtype=fileupload`` and ``time=<ttl>`` and returns the URL as plain text.
    No API key or signup required. Returned URLs are served from ``litter.catbox.moe``.
    Used wherever a public HTTPS URL is needed briefly for content that is otherwise
    only available as in-process bytes (e.g. Instagram ``image_url`` publishing).
    """
    try:
        response = requests.post(
            LITTERBOX_API_URL,
            data={"reqtype": "fileupload", "time": LITTERBOX_TTL},
            files={"fileToUpload": (filename, image_bytes, "image/jpeg")},
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise LitterboxUploadError(f"litterbox upload failed for {filename!r}: {exc}") from exc

    if response.status_code != HTTPStatus.OK:
        raise LitterboxUploadError(
            f"litterbox upload failed for {filename!r}: HTTP {response.status_code} — {response.text[:200]}"
        )

    url = response.text.strip()
    if not url.startswith("https://"):
        raise LitterboxUploadError(f"litterbox returned unexpected response for {filename!r}: {url[:200]!r}")

    logger.debug(f"Uploaded {filename!r} to litterbox: {url}")
    return url


def upload_to_uguu(image_bytes: bytes, filename: str = "image.jpg") -> str:
    """Upload bytes to uguu.se anonymously and return the public HTTPS URL.

    uguu.se is operated independently of catbox.moe, so it stays up when the whole
    catbox/litterbox vendor is down (the class of failure behind #48). Files are
    deleted after 3 hours. Accepts a multipart POST with a ``files[]`` field and
    answers JSON: ``{"success": true, "files": [{"url": "https://d.uguu.se/..."}]}``.
    No API key or signup required. The content type is guessed from ``filename``.
    """
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        response = requests.post(
            UGUU_API_URL,
            files={"files[]": (filename, image_bytes, content_type)},
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise UguuUploadError(f"uguu upload failed for {filename!r}: {exc}") from exc

    if response.status_code != HTTPStatus.OK:
        raise UguuUploadError(
            f"uguu upload failed for {filename!r}: HTTP {response.status_code} — {response.text[:200]}"
        )

    try:
        payload = response.json()
        url = payload["files"][0]["url"] if payload.get("success") else ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise UguuUploadError(f"uguu returned unexpected response for {filename!r}: {exc}") from exc

    if not isinstance(url, str) or not url.startswith("https://"):
        raise UguuUploadError(f"uguu returned unexpected response for {filename!r}: {url!r}"[:300])

    logger.debug(f"Uploaded {filename!r} to uguu: {url}")
    return url


# Each name has an ``upload_to_<name>(bytes, filename) -> https URL`` function in this module.
IMAGE_HOST_PROVIDERS_AVAILABLE = ("litterbox", "uguu")


def _uploader(name: str) -> Callable[[bytes, str], str]:
    """Resolve the provider function at call time, so ``commons.functions.upload_to_<name>`` can be patched."""
    return globals()[f"upload_to_{name}"]


def upload_to_public_image_host(
    image_bytes: bytes,
    filename: str = "image.jpg",
    providers: Sequence[str] | None = None,
) -> str:
    """Upload bytes to the first working public image host and return its HTTPS URL.

    ``providers`` names entries of ``IMAGE_HOST_PROVIDERS_AVAILABLE`` and defaults to
    ``settings.IMAGE_HOST_PROVIDERS`` (env ``IMAGE_HOST_PROVIDERS``, comma separated).
    Each provider is tried once, in order; a failure is logged at WARNING and the
    next provider is tried. When every provider fails, ``ImageHostUploadError`` is
    raised with each provider's reason, chained to the last failure.
    """
    if providers is None:
        from django.conf import settings  # noqa: PLC0415 — keep commons.functions importable without Django

        names: Sequence[str] = tuple(settings.IMAGE_HOST_PROVIDERS)
    else:
        names = tuple(providers)

    unknown = [name for name in names if name not in IMAGE_HOST_PROVIDERS_AVAILABLE]
    if unknown or not names:
        raise ValueError(
            f"IMAGE_HOST_PROVIDERS must name at least one of {list(IMAGE_HOST_PROVIDERS_AVAILABLE)}; "
            f"got {list(names)!r} (unknown: {unknown!r})"
        )

    failures: list[str] = []
    last_error: ImageHostUploadError | None = None
    for name in names:
        try:
            return _uploader(name)(image_bytes, filename)
        except ImageHostUploadError as exc:
            logger.warning(f"image host {name!r} failed for {filename!r} ({type(exc).__name__}): {exc}")
            failures.append(f"{name}: {exc}")
            last_error = exc

    raise ImageHostUploadError(f"all image hosts failed for {filename!r}: " + "; ".join(failures)) from last_error


def get_month_end(month_start: datetime.date) -> datetime.date:
    """Return the first day of the next month after ``month_start``."""
    if month_start.month == 12:  # noqa: PLR2004
        return month_start.replace(year=month_start.year + 1, month=1, day=1)
    return month_start.replace(month=month_start.month + 1, day=1)


def parse_month(value: str | None, default_to_next_month: bool = False) -> datetime.date:
    """
    Parse a month string into a date (first day of the month).

    Args:
        value: Date string in 'YYYY-MM' or 'YYYY-MM-DD' format, or None for default.
        default_to_next_month: If True and value is None, return next month.
                               If False and value is None, return current month.

    Returns:
        A date object representing the first day of the target month.

    Raises:
        ValueError: If the date format is invalid.
    """
    if value is None:
        today = datetime.date.today()  # noqa: DTZ011
        if default_to_next_month:
            return get_month_end(datetime.date(today.year, today.month, 1))
        return datetime.date(today.year, today.month, 1)

    value = value.strip()
    if len(value) == YYYY_MM_LENGTH:  # YYYY-MM
        return datetime.datetime.strptime(value, "%Y-%m").date()  # noqa: DTZ007
    if len(value) == YYYY_MM_DD_LENGTH:  # YYYY-MM-DD
        parsed = datetime.datetime.strptime(value, "%Y-%m-%d").date()  # noqa: DTZ007
        return parsed.replace(day=1)
    raise ValueError(f"Invalid date format: {value}. Expected 'YYYY-MM' or 'YYYY-MM-DD'")


def parse_week(value: str | None, default_to_next_week: bool = False) -> datetime.date:
    """
    Parse a week string into a date (Monday of the week).

    Args:
        value: Date string in 'YYYY-MM-DD' format (must be a Monday), or None for default.
        default_to_next_week: If True and value is None, return next week's Monday.
                              If False and value is None, return current week's Monday.

    Returns:
        A date object representing the Monday of the target week.

    Raises:
        ValueError: If the date format is invalid or is not a Monday.
    """
    if value is None:
        today = datetime.date.today()  # noqa: DTZ011
        # Calculate current week's Monday (weekday 0 = Monday)
        days_since_monday = today.weekday()
        current_monday = today - datetime.timedelta(days=days_since_monday)
        if default_to_next_week:
            return current_monday + datetime.timedelta(weeks=1)
        return current_monday

    value = value.strip()
    if len(value) != YYYY_MM_DD_LENGTH:
        raise ValueError(f"Invalid date format: {value}. Expected 'YYYY-MM-DD' format (must be a Monday)")

    parsed = datetime.datetime.strptime(value, "%Y-%m-%d").date()  # noqa: DTZ007

    # Validate that the date is a Monday (weekday 0)
    if parsed.weekday() != 0:
        day_name = parsed.strftime("%A")
        raise ValueError(f"Date {value} is a {day_name}, but must be a Monday")

    return parsed
