"""C3-A repository boundary (protocol only; no implementation before C3-B).

All acceptance operations must be atomic in future API/PostgreSQL code.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.models.source_heartbeat import SourceHeartbeatRequest, SourceHeartbeatResponse
from app.models.source_authority import (
    AuthorityGrantView,
    ManagedSnapshotAcceptanceResult,
    PublishUnderCurrentGrant,
    SourceAuthorityRecord,
    SourceHeartbeatRecord,
    Source,
    TransitionCandidate,
)


class SourceAuthorityRepository(Protocol):
    """Separate managed write from candidate transition; device-scoped authority."""

    def get_source_authority(self, device_id: str) -> SourceAuthorityRecord | None: ...

    def bootstrap_managed_source_authority(
        self, device_id: str,
    ) -> ManagedSnapshotAcceptanceResult: ...

    def return_source_authority_to_legacy(
        self, device_id: str,
    ) -> SourceAuthorityRecord | None: ...

    def accept_current_grant_snapshot(
        self, command: PublishUnderCurrentGrant,
    ) -> ManagedSnapshotAcceptanceResult: ...

    def accept_transition_candidate(
        self, command: TransitionCandidate,
    ) -> ManagedSnapshotAcceptanceResult: ...

    def get_current_grant(self, device_id: str) -> AuthorityGrantView | None: ...


class SourceHeartbeatRepository(Protocol):
    """C3-C source heartbeat contract; PostgreSQL remains the authority arbiter."""

    def get_source_heartbeat(
        self, device_id: str, source: Source, instance_id: UUID,
    ) -> SourceHeartbeatRecord | None: ...

    def record_source_heartbeat(
        self,
        device_id: str,
        source: Source,
        request: SourceHeartbeatRequest,
        *,
        cloud_binding_id: UUID | None = None,
    ) -> SourceHeartbeatResponse: ...
