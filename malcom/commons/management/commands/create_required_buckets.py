import json
from pathlib import Path

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management import BaseCommand, CommandParser
from django.utils.translation import gettext_lazy as _

from malcom.awsclients import S3_CLIENT

COMMANDS_DIR = Path(__file__).parent.resolve()
CORS_CONFIG_FILEPATH = COMMANDS_DIR / "s3-direct-bucket-cors.json"
REQUIRED_BUCKET_NAMES = (settings.S3_DIRECT_BUCKET,)


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--dry-run", action="store_true", default=False, help=_("If given buckets will NOT be created!")
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003  # noqa: C901, PLR0912, PLR0915, PLR0911
        for bucket_name in REQUIRED_BUCKET_NAMES:
            self.stdout.write(f"Creating Bucket({bucket_name})...")
            try:
                response = S3_CLIENT.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={
                        "LocationConstraint": settings.AWS_REGION,
                    },
                )
                self.stdout.write(str(response))
            except ClientError as e:
                if any(text in str(e.args) for text in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou")):
                    self.stderr.write(f"Creating Bucket({bucket_name})... ALREADY EXISTS!")
                else:
                    # not sure, re-raise
                    raise

            assert CORS_CONFIG_FILEPATH.exists(), f"{CORS_CONFIG_FILEPATH} not found!"
            cors_config_raw = CORS_CONFIG_FILEPATH.read_text(encoding="utf8")
            cors_config_json = json.loads(cors_config_raw)
            self.stdout.write(f"settings CORS for Bucket({bucket_name}) ...")
            S3_CLIENT.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_config_json)
            self.stdout.write(f"settings CORS for Bucket({bucket_name}) ... DONE!")
