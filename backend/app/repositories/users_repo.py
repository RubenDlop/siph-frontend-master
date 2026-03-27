from __future__ import annotations

from typing import Optional

from boto3.dynamodb.conditions import Key

from ..core.dynamo import table, now_iso, next_id, to_dynamo, from_dynamo


def _users():
    return table("users")


def _clean_item(data: dict) -> dict:
    """
    DynamoDB no debe recibir atributos None para claves/indexes como azure_oid.
    También evitamos strings vacíos en campos opcionales.
    """
    cleaned: dict = {}
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        cleaned[key] = value
    return cleaned


def get_user_by_email(email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    if not email:
        return None

    res = _users().get_item(Key={"email": email})
    item = res.get("Item")
    return from_dynamo(item) if item else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    res = _users().query(
        IndexName="id-index",
        KeyConditionExpression=Key("id").eq(int(user_id)),
        Limit=1,
    )
    items = res.get("Items", [])
    return from_dynamo(items[0]) if items else None


def get_user_by_azure_oid(azure_oid: str) -> Optional[dict]:
    azure_oid = (azure_oid or "").strip()
    if not azure_oid:
        return None

    res = _users().query(
        IndexName="azure_oid-index",
        KeyConditionExpression=Key("azure_oid").eq(azure_oid),
        Limit=1,
    )
    items = res.get("Items", [])
    return from_dynamo(items[0]) if items else None


def create_local_user(
    *,
    first_name: str,
    last_name: str,
    email: str,
    password_hash: str,
    role: str = "USER",
) -> dict:
    email = (email or "").strip().lower()

    item = _clean_item(
        {
            "email": email,  # PK
            "id": next_id("users"),
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "password_hash": password_hash,
            "auth_provider": "LOCAL",
            "role": role,
            "is_active": True,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )

    _users().put_item(
        Item=to_dynamo(item),
        ConditionExpression="attribute_not_exists(email)",
    )
    return item


def upsert_google_user(
    *,
    email: str,
    first_name: str,
    last_name: str,
    password_hash: str,
) -> dict:
    email = (email or "").strip().lower()
    existing = get_user_by_email(email)

    if existing:
        _users().update_item(
            Key={"email": email},
            UpdateExpression="""
                SET first_name = :first_name,
                    last_name = :last_name,
                    auth_provider = :auth_provider,
                    updated_at = :updated_at
            """,
            ExpressionAttributeValues={
                ":first_name": first_name or existing.get("first_name") or "Usuario",
                ":last_name": last_name or existing.get("last_name") or "Google",
                ":auth_provider": "GOOGLE",
                ":updated_at": now_iso(),
            },
        )
        return get_user_by_email(email)

    item = _clean_item(
        {
            "email": email,
            "id": next_id("users"),
            "first_name": (first_name or "Usuario").strip(),
            "last_name": (last_name or "Google").strip(),
            "password_hash": password_hash,
            "auth_provider": "GOOGLE",
            "role": "USER",
            "is_active": True,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )

    _users().put_item(
        Item=to_dynamo(item),
        ConditionExpression="attribute_not_exists(email)",
    )
    return item


def upsert_azure_user(
    *,
    email: str,
    first_name: str,
    last_name: str,
    azure_oid: str,
    azure_tid: str,
    password_hash: str,
    role: str = "USER",
) -> dict:
    email = (email or "").strip().lower()

    existing = get_user_by_email(email)
    if existing:
        _users().update_item(
            Key={"email": email},
            UpdateExpression="""
                SET first_name = :first_name,
                    last_name = :last_name,
                    azure_oid = :azure_oid,
                    azure_tid = :azure_tid,
                    auth_provider = :auth_provider,
                    #role = :role,
                    updated_at = :updated_at
            """,
            ExpressionAttributeNames={
                "#role": "role",
            },
            ExpressionAttributeValues={
                ":first_name": first_name or existing.get("first_name") or "Usuario",
                ":last_name": last_name or existing.get("last_name") or "Microsoft",
                ":azure_oid": azure_oid,
                ":azure_tid": azure_tid,
                ":auth_provider": "AZURE",
                ":role": role,
                ":updated_at": now_iso(),
            },
        )
        return get_user_by_email(email)

    item = _clean_item(
        {
            "email": email,
            "id": next_id("users"),
            "first_name": (first_name or "Usuario").strip(),
            "last_name": (last_name or "Microsoft").strip(),
            "password_hash": password_hash,
            "azure_oid": azure_oid,
            "azure_tid": azure_tid,
            "auth_provider": "AZURE",
            "role": role,
            "is_active": True,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    )

    _users().put_item(
        Item=to_dynamo(item),
        ConditionExpression="attribute_not_exists(email)",
    )
    return item


def update_user_role_by_email(email: str, role: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    _users().update_item(
        Key={"email": email},
        UpdateExpression="SET #role = :role, updated_at = :updated_at",
        ExpressionAttributeNames={"#role": "role"},
        ExpressionAttributeValues={
            ":role": role,
            ":updated_at": now_iso(),
        },
    )
    return get_user_by_email(email)
