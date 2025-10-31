import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock

from botocore.exceptions import ClientError
from django.conf import settings

from malcom.awsclients import S3_CLIENT, S3_RESOURCE

CORS_FILEPATH = Path(__file__).parent.parent / "management" / "commands" / "s3-direct-bucket-cors.json"


class MockRequest:
    GET = {}
    POST = {}
    path = ""
    _messages = MagicMock()

    def __init__(self, *args, **kwargs) -> None:
        self.GET = {}
        self.POST = {}
        self.META = {}
        self._messages = MagicMock()

    def get_full_path(self):
        return self.path


def reset_buckets() -> list[str | None]:
    """
    Ensure a empty bucket.

    Create a newly s3 bucket if it does not exists and remove all items.
    """
    assert CORS_FILEPATH.exists(), f"{CORS_FILEPATH} not found!"
    cors_config_raw = CORS_FILEPATH.read_text(encoding="utf8")
    cors_config_json = json.loads(cors_config_raw)

    buckets = []
    for bucket_name in settings.REQUIRED_BUCKETS:
        with contextlib.suppress(ClientError):
            S3_RESOURCE.create_bucket(
                Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": settings.AWS_DEFAULT_REGION}
            )
        S3_RESOURCE.Bucket(bucket_name).objects.all().delete()
        buckets.append(bucket_name)
        S3_CLIENT.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_config_json)

    return buckets
