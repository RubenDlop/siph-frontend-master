from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from .config import settings


@lru_cache
def dynamodb_resource():
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
        "config": Config(
            retries={"max_attempts": 10, "mode": "standard"},
            connect_timeout=5,
            read_timeout=10,
        ),
    }

    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url

    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id

    if settings.aws_secret_access_key:
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    return boto3.resource("dynamodb", **kwargs)


@lru_cache
def dynamodb_client():
    return dynamodb_resource().meta.client


def table_name(base_name: str) -> str:
    return f"{settings.dynamodb_table_prefix}{base_name}"


def table(base_name: str):
    return dynamodb_resource().Table(table_name(base_name))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo(v) for v in value]
    return value


def from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_dynamo(v) for v in value]
    return value


def next_id(entity: str) -> int:
    res = table("counters").update_item(
        Key={"entity": entity},
        UpdateExpression="SET #v = if_not_exists(#v, :zero) + :inc",
        ExpressionAttributeNames={"#v": "value"},
        ExpressionAttributeValues={":zero": 0, ":inc": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(res["Attributes"]["value"])
