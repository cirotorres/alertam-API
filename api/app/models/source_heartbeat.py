"""C3-C server-owned source health API contract (not a snapshot writer)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator

from app.models.source_authority import (
    AuthorityGrantView, AuthorityReasonCode, AuthorityStatus, Source,
)


class SourceHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    instance_id: UUID
    process_healthy: bool = True
    collection_healthy: bool
    last_reported_generated_at: AwareDatetime | None = None
    last_candidate_generated_at: AwareDatetime | None = None
    persistent_state_ready: bool | None = None


class SourceHeartbeatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)

    status: AuthorityStatus
    source: Source
    instance_id: UUID
    reason_code: AuthorityReasonCode | None = None
    grant: AuthorityGrantView | None = None
    renewed: bool = False

    @model_validator(mode="after")
    def validate_grant(self) -> "SourceHeartbeatResponse":
        if self.grant is not None and (
            self.grant.source != self.source
            or self.grant.holder_instance_id != self.instance_id
        ):
            raise ValueError("heartbeat grant identity mismatch")
        if self.renewed and self.grant is None:
            raise ValueError("renewal must return current holder's grant")
        return self
