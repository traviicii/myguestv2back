import json
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_str_list(value: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]

    raw = value.strip()
    if not raw:
        return []

    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("Expected a JSON array.")
        return [str(item).strip() for item in parsed if str(item).strip()]

    return [item.strip() for item in raw.split(",") if item.strip()]


def _normalize_trusted_host(value: str) -> str:
    if value == "*":
        return value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.hostname or parsed.path
    return host.strip().lower()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "MyGuest API v2"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/myguestv2"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8081"])
    cors_allow_credentials: bool = False
    trusted_hosts: list[str] = Field(default_factory=list)
    api_docs_enabled: bool | None = None
    firebase_credentials_path: str | None = None
    firebase_storage_bucket: str | None = None

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Accept raw Render-style URLs and normalize to SQLAlchemy psycopg driver syntax.
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str] | tuple[str, ...]) -> list[str]:
        origins = _parse_str_list(value)
        return [origin.rstrip("/") for origin in origins]

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value: str | list[str] | tuple[str, ...]) -> list[str]:
        hosts = _parse_str_list(value)
        return [_normalize_trusted_host(host) for host in hosts]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def expose_api_docs(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return not self.is_production

    @property
    def resolved_trusted_hosts(self) -> list[str]:
        if self.trusted_hosts:
            return self.trusted_hosts
        if self.is_production:
            return []
        return ["localhost", "127.0.0.1", "testserver"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
