from __future__ import annotations

import time

from botocore.exceptions import ClientError

from ..core.dynamo import dynamodb_client, table_name

client = dynamodb_client()


def table_exists(name: str) -> bool:
    try:
        client.describe_table(TableName=name)
        return True
    except client.exceptions.ResourceNotFoundException:
        return False
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code == "ResourceNotFoundException":
            return False
        raise


def wait_until_active(name: str, timeout_seconds: int = 60) -> None:
    started = time.time()

    while time.time() - started < timeout_seconds:
        try:
            res = client.describe_table(TableName=name)
            status = res["Table"]["TableStatus"]
            if status == "ACTIVE":
                return
        except client.exceptions.ResourceNotFoundException:
            pass
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code != "ResourceNotFoundException":
                raise

        time.sleep(1)

    raise TimeoutError(f"La tabla {name} no llegó a estado ACTIVE en {timeout_seconds}s.")


def gsi(index_name: str, key_schema: list[dict], projection_type: str = "ALL") -> dict:
    return {
        "IndexName": index_name,
        "KeySchema": key_schema,
        "Projection": {"ProjectionType": projection_type},
    }


def create_table(
    *,
    name: str,
    key_schema: list[dict],
    attribute_definitions: list[dict],
    global_secondary_indexes: list[dict] | None = None,
) -> None:
    if table_exists(name):
        print(f"[SKIP] La tabla ya existe: {name}")
        return

    payload = {
        "TableName": name,
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": key_schema,
        "AttributeDefinitions": attribute_definitions,
    }

    if global_secondary_indexes:
        payload["GlobalSecondaryIndexes"] = global_secondary_indexes

    client.create_table(**payload)
    wait_until_active(name)
    print(f"[OK] Tabla creada: {name}")


def main() -> None:
    # =========================
    # COUNTERS
    # =========================
    create_table(
        name=table_name("counters"),
        key_schema=[
            {"AttributeName": "entity", "KeyType": "HASH"},
        ],
        attribute_definitions=[
            {"AttributeName": "entity", "AttributeType": "S"},
        ],
    )

    # =========================
    # USERS
    # PK: email
    # GSIs: id-index, azure_oid-index, role-created_at-index
    # =========================
    create_table(
        name=table_name("users"),
        key_schema=[
            {"AttributeName": "email", "KeyType": "HASH"},
        ],
        attribute_definitions=[
            {"AttributeName": "email", "AttributeType": "S"},
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "azure_oid", "AttributeType": "S"},
            {"AttributeName": "role", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        global_secondary_indexes=[
            gsi(
                "id-index",
                [
                    {"AttributeName": "id", "KeyType": "HASH"},
                ],
            ),
            gsi(
                "azure_oid-index",
                [
                    {"AttributeName": "azure_oid", "KeyType": "HASH"},
                ],
            ),
            gsi(
                "role-created_at-index",
                [
                    {"AttributeName": "role", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # SERVICE REQUESTS
    # PK: id
    # GSIs:
    # - user_id-updated_at-index
    # - assigned_worker_id-updated_at-index
    # - status-created_at-index
    # =========================
    create_table(
        name=table_name("service_requests"),
        key_schema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        attribute_definitions=[
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "user_id", "AttributeType": "N"},
            {"AttributeName": "assigned_worker_id", "AttributeType": "N"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
            {"AttributeName": "updated_at", "AttributeType": "S"},
        ],
        global_secondary_indexes=[
            gsi(
                "user_id-updated_at-index",
                [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "updated_at", "KeyType": "RANGE"},
                ],
            ),
            gsi(
                "assigned_worker_id-updated_at-index",
                [
                    {"AttributeName": "assigned_worker_id", "KeyType": "HASH"},
                    {"AttributeName": "updated_at", "KeyType": "RANGE"},
                ],
            ),
            gsi(
                "status-created_at-index",
                [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # REQUEST MESSAGES
    # PK: request_id
    # SK: id
    # GSI: sender_user_id-id-index
    # =========================
    create_table(
        name=table_name("request_messages"),
        key_schema=[
            {"AttributeName": "request_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "request_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "sender_user_id", "AttributeType": "N"},
        ],
        global_secondary_indexes=[
            gsi(
                "sender_user_id-id-index",
                [
                    {"AttributeName": "sender_user_id", "KeyType": "HASH"},
                    {"AttributeName": "id", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # REQUEST EVENTS
    # PK: request_id
    # SK: id
    # GSI: actor_user_id-id-index
    # =========================
    create_table(
        name=table_name("request_events"),
        key_schema=[
            {"AttributeName": "request_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "request_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "actor_user_id", "AttributeType": "N"},
        ],
        global_secondary_indexes=[
            gsi(
                "actor_user_id-id-index",
                [
                    {"AttributeName": "actor_user_id", "KeyType": "HASH"},
                    {"AttributeName": "id", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # REQUEST REVIEWS
    # PK: request_id
    # SK: reviewer_user_id
    # GSI: reviewee_user_id-created_at-index
    # =========================
    create_table(
        name=table_name("request_reviews"),
        key_schema=[
            {"AttributeName": "request_id", "KeyType": "HASH"},
            {"AttributeName": "reviewer_user_id", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "request_id", "AttributeType": "N"},
            {"AttributeName": "reviewer_user_id", "AttributeType": "N"},
            {"AttributeName": "reviewee_user_id", "AttributeType": "N"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        global_secondary_indexes=[
            gsi(
                "reviewee_user_id-created_at-index",
                [
                    {"AttributeName": "reviewee_user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # WORKER APPLICATIONS
    # PK: id
    # GSIs:
    # - user_id-created_at-index
    # - status-created_at-index
    # =========================
    create_table(
        name=table_name("worker_applications"),
        key_schema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        attribute_definitions=[
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "user_id", "AttributeType": "N"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        global_secondary_indexes=[
            gsi(
                "user_id-created_at-index",
                [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
            gsi(
                "status-created_at-index",
                [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # TECHNICIAN PROFILES
    # PK: user_id
    # GSI: city-user_id-index
    # =========================
    create_table(
        name=table_name("technician_profiles"),
        key_schema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
        ],
        attribute_definitions=[
            {"AttributeName": "user_id", "AttributeType": "N"},
            {"AttributeName": "city", "AttributeType": "S"},
        ],
        global_secondary_indexes=[
            gsi(
                "city-user_id-index",
                [
                    {"AttributeName": "city", "KeyType": "HASH"},
                    {"AttributeName": "user_id", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # VERIFICATION CASES
    # PK: id
    # GSIs:
    # - tech_id-created_at-index
    # - user_id-created_at-index
    # =========================
    create_table(
        name=table_name("verification_cases"),
        key_schema=[
            {"AttributeName": "id", "KeyType": "HASH"},
        ],
        attribute_definitions=[
            {"AttributeName": "id", "AttributeType": "N"},
            {"AttributeName": "tech_id", "AttributeType": "N"},
            {"AttributeName": "user_id", "AttributeType": "N"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        global_secondary_indexes=[
            gsi(
                "tech_id-created_at-index",
                [
                    {"AttributeName": "tech_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
            gsi(
                "user_id-created_at-index",
                [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
            ),
        ],
    )

    # =========================
    # VERIFICATION DOCUMENTS
    # PK: case_id
    # SK: id
    # =========================
    create_table(
        name=table_name("verification_documents"),
        key_schema=[
            {"AttributeName": "case_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "case_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
        ],
    )

    # =========================
    # VERIFICATION AUDIT LOGS
    # PK: case_id
    # SK: id
    # =========================
    create_table(
        name=table_name("verification_audit_logs"),
        key_schema=[
            {"AttributeName": "case_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "case_id", "AttributeType": "N"},
            {"AttributeName": "id", "AttributeType": "N"},
        ],
    )

    print("\n✅ Todas las tablas DynamoDB fueron verificadas/creadas correctamente.")


if __name__ == "__main__":
    main()
