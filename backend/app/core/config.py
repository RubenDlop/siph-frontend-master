from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # =========================
    # DYNAMODB
    # =========================
    aws_region: str = Field(
        default="us-east-1",
        validation_alias="AWS_REGION",
    )
    aws_access_key_id: Optional[str] = Field(
        default=None,
        validation_alias="AWS_ACCESS_KEY_ID",
    )
    aws_secret_access_key: Optional[str] = Field(
        default=None,
        validation_alias="AWS_SECRET_ACCESS_KEY",
    )
    dynamodb_endpoint_url: Optional[str] = Field(
        default=None,
        validation_alias="DYNAMODB_ENDPOINT_URL",
    )
    dynamodb_table_prefix: str = Field(
        default="siph_",
        validation_alias="DYNAMODB_TABLE_PREFIX",
    )

    jwt_secret_key: str = Field(
        default="change-me",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
    )
    jwt_expiration_minutes: int = Field(
        default=60,
        validation_alias="JWT_EXPIRATION_MINUTES",
    )

    google_client_id: Optional[str] = Field(
        default=None,
        validation_alias="GOOGLE_CLIENT_ID",
    )

    azure_tenant_id: Optional[str] = Field(
        default=None,
        validation_alias="AZURE_TENANT_ID",
    )
    azure_spa_client_id: Optional[str] = Field(
        default=None,
        validation_alias="AZURE_SPA_CLIENT_ID",
    )
    azure_api_client_id: Optional[str] = Field(
        default=None,
        validation_alias="AZURE_API_CLIENT_ID",
    )
    azure_authority: Optional[str] = Field(
        default=None,
        validation_alias="AZURE_AUTHORITY",
    )
    azure_api_scope: Optional[str] = Field(
        default=None,
        validation_alias="AZURE_API_SCOPE",
    )

    manychat_shared_secret: Optional[str] = Field(
        default=None,
        validation_alias="MANYCHAT_SHARED_SECRET",
    )


settings = Settings()
