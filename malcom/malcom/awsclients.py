import fnmatch
from http import HTTPStatus

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

config = Config(
    region_name=settings.AWS_REGION,
    connect_timeout=3,
    retries={"max_attempts": 5},
    s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
)

S3_CLIENT = boto3.client("s3", config=config, endpoint_url=settings.AWS_SERVICE_ENDPOINTS["s3"])
S3_RESOURCE = boto3.resource("s3", config=config, endpoint_url=settings.AWS_SERVICE_ENDPOINTS["s3"])


def s3_key_exists(bucket: str, key: str) -> bool:
    """Check if given bucket, key exists"""
    exists = None
    try:
        S3_CLIENT.head_object(Bucket=bucket, Key=key)
        exists = True
    except ClientError as e:
        if e.response["ResponseMetadata"]["HTTPStatusCode"] == HTTPStatus.NOT_FOUND:
            exists = False
        else:
            raise
    return exists


def s3_glob(pattern: str, prefix: str | None = None) -> list:
    """
    S3にたいして、pathと同じようにpatternにmatchしているキーをfilterしてs3.ObjectSummaryを返す

    s3.ObjectSummary:
        class ObjectSummary:
            bucket_name
            key
            last_modified
            owner
            size
            storage_class
    """
    bucket = S3_RESOURCE.Bucket(settings.CSV_DOWNLOAD_BUCKETNAME)
    matched_key_objects = []

    kwargs = {}
    if prefix:
        kwargs["Prefix"] = prefix

    for key_object in bucket.objects.filter(**kwargs):
        filename = key_object.key.split("/")[-1]
        if fnmatch.fnmatch(filename, pattern):
            matched_key_objects.append(key_object)
    return matched_key_objects
