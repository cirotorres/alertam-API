from __future__ import annotations

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from app.repositories.cloud_bindings import CloudBindingStatus


_CREDENTIAL_RE = re.compile(r"^[A-Za-z0-9_-]{43,86}$")


class CloudBindingCredentialRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    credential: SecretStr

    @field_validator("credential")
    @classmethod
    def validate_credential(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not _CREDENTIAL_RE.fullmatch(raw):
            raise ValueError("Cloud credential inválida.")
        return value


class CloudBindingEnsureRequest(CloudBindingCredentialRequest):
    realm_id: str


class CloudBindingResponse(BaseModel):
    cloud_binding_id: UUID
    device_id: str
    realm_id: str
    credential_version: int
    status: CloudBindingStatus
    device_enabled: bool
    realm_authorized: bool
    usable: bool
