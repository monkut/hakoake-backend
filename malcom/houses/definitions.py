from commons.definitions import StringEnumWithChoices


class WebsiteProcessingState(StringEnumWithChoices):
    """Enum representing the state of website processing."""

    NOT_STARTED = "not_started"  # noqa: N806
    IN_PROGRESS = "in_progress"  # noqa: N806
    COMPLETED = "completed"  # noqa: N806
    FAILED = "failed"  # noqa: N806


class CrawlerCollectionState(StringEnumWithChoices):
    """Enum representing the state of crawler collection for a live house."""

    PENDING = "pending"  # noqa: N806
    SUCCESS = "success"  # noqa: N806
    ERROR = "error"  # noqa: N806
    TIMEOUT = "timeout"  # noqa: N806
