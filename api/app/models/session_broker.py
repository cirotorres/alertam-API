from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class ProviderScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    scope_id: str = Field(min_length=1, max_length=80)
    schema_version: int = Field(gt=0)
    capabilities: tuple[str, ...] = Field(default=(), max_length=32)

    @field_validator("scope_id")
    @classmethod
    def normalize_scope_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("scope_id não pode ser vazio")
        return normalized

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({str(item).strip() for item in value if str(item).strip()}))
        if len(normalized) != len(value):
            raise ValueError("capabilities devem ser únicas e não vazias")
        return normalized


class SessionPublisherRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    realm_id: str = Field(min_length=1, max_length=120)
    publisher_id: UUID
    provider_scope: ProviderScopeRequest


class SessionCookieIn(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    name: str = Field(min_length=1, max_length=128)
    value: SecretStr = Field(
        min_length=1,
        max_length=4096,
        json_schema_extra={"writeOnly": True},
    )
    expiry: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def normalize_cookie_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("cookie name não pode ser vazio")
        return normalized


class SessionLeasePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    realm_id: str = Field(min_length=1, max_length=120)
    publisher_id: UUID
    local_generation: int = Field(gt=0)
    expires_at: datetime | None = None
    cookies: tuple[SessionCookieIn, ...] = Field(min_length=1, max_length=64)

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at precisa de timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def reject_duplicate_cookie_names(self) -> "SessionLeasePublishRequest":
        names = [cookie.name for cookie in self.cookies]
        if len(names) != len(set(names)):
            raise ValueError("cookie names duplicados")
        return self


class SessionLeaseRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    realm_id: str = Field(min_length=1, max_length=120)
    lease_id: UUID


class SessionLeaseInvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_id: UUID
    realm_epoch: int = Field(gt=0)


class SessionCookieOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: str = Field(repr=False)
    expiry: int | None = None


class SessionPublisherRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    realm_id: str = Field(min_length=1, max_length=120)
    publisher_id: UUID


class SessionPublisherResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publisher_id: UUID
    realm_id: str
    device_id: str
    provider_scope: ProviderScopeRequest
    scope_status: str
    last_generation: int
    status: str


class AcceptedSessionLeaseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_id: UUID
    realm_id: str
    publisher_id: UUID
    local_generation: int
    realm_epoch: int
    received_at: datetime
    expires_at: datetime | None
    status: str


class SessionLeaseConsumeResponse(AcceptedSessionLeaseMetadata):
    cookies: tuple[SessionCookieOut, ...]
