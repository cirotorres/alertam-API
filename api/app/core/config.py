from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    persistence_backend: Literal["memory", "supabase"] = "memory"

    supabase_url: str = ""
    supabase_secret_key: str = Field(default="", repr=False)
    supabase_service_role_key: str = Field(default="", repr=False)

    stale_after_seconds: int = 120
    allowed_origins: str = ""
    log_level: str = "INFO"

    mock_seed_device: bool = True
    mock_device_id: str = "pecem-01"
    mock_device_secret: str = Field(
        default="change-this-local-device-secret",
        repr=False,
    )
    mock_view_secret: str = Field(
        default="change-this-local-view-secret",
        repr=False,
    )

    @property
    def supabase_server_key(self) -> str:
        return (
            self.supabase_secret_key.strip()
            or self.supabase_service_role_key.strip()
        )

    @model_validator(mode="after")
    def validate_persistence_credentials(self) -> "Settings":
        if self.persistence_backend != "supabase":
            return self

        missing: list[str] = []
        if not self.supabase_url.strip():
            missing.append("SUPABASE_URL")
        if not self.supabase_server_key:
            missing.append(
                "SUPABASE_SECRET_KEY "
                "(ou SUPABASE_SERVICE_ROLE_KEY legado)"
            )
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Supabase requer: {joined}")
        return self
