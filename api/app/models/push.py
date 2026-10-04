from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class PushSubscriptionKeysIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str = Field(min_length=1, max_length=4096)
    auth: str = Field(min_length=1, max_length=4096)


class PushSubscriptionIn(BaseModel):
    # Unknown fields such as a client-supplied device_id are ignored.
    # The authenticated mobile session is always authoritative.
    model_config = ConfigDict(extra="ignore")

    endpoint: str = Field(min_length=1, max_length=4096)
    keys: PushSubscriptionKeysIn

    @field_validator("endpoint")
    @classmethod
    def validate_push_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Endpoint Web Push inválido.")

        hostname = parsed.hostname.rstrip(".").casefold()
        if (
            hostname == "localhost"
            or hostname.endswith(".localhost")
            or hostname.endswith(".local")
            or hostname.endswith(".internal")
        ):
            raise ValueError("Endpoint Web Push inválido.")

        try:
            address = ip_address(hostname)
        except ValueError:
            return value
        if not address.is_global:
            raise ValueError("Endpoint Web Push inválido.")
        return value


class PushPreferencesResponse(BaseModel):
    confirmed: bool
    updated: bool
    completed: bool
    cancelled: bool
    anchored: bool


class PushPreferencesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool | None = None
    updated: bool | None = None
    completed: bool | None = None
    cancelled: bool | None = None
    anchored: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_preference(self) -> "PushPreferencesPatch":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos uma preferência.")
        return self


class PushInstallationResponse(BaseModel):
    installation_id: UUID
    active: bool
    preferences: PushPreferencesResponse
    push_enabled_at: AwareDatetime
    last_seen_at: AwareDatetime
    last_foreground_at: AwareDatetime | None


class VapidPublicKeyResponse(BaseModel):
    enabled: bool
    public_key: str | None
