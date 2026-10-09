"""C3-A domain contracts only. No clocks, persistence, RPC or operational writers."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Source(StrEnum):
    DESKTOP = "desktop"
    CLOUD = "cloud"


class AuthorityMode(StrEnum):
    LEGACY = "legacy"
    MANAGED = "managed"


class AuthorityStatus(StrEnum):
    ACCEPTED = "accepted"
    IDEMPOTENT = "idempotent"
    FENCED = "authority_fenced"
    REJECTED = "rejected"
    INELIGIBLE = "ineligible"


class AuthorityReasonCode(StrEnum):
    LEGACY_MODE = "legacy_mode"
    DESKTOP_HEALTHY = "desktop_healthy"
    DESKTOP_DEGRADED = "desktop_degraded"
    DESKTOP_STALE = "desktop_stale"
    DESKTOP_SNAPSHOT_STALE = "desktop_snapshot_stale"
    DESKTOP_OFFLINE = "desktop_offline"
    CLOUD_SNAPSHOT_STALE = "cloud_snapshot_stale"
    CLOUD_AUTH_UNAVAILABLE = "cloud_auth_unavailable"
    CLOUD_BINDING_UNUSABLE = "cloud_binding_unusable"
    CLOUD_PERSISTENT_STATE_UNAVAILABLE = "cloud_persistent_state_unavailable"
    CLOUD_STANDBY_STALE = "cloud_standby_stale"
    FAILOVER_WAIT_HYSTERESIS = "failover_wait_hysteresis"
    FAILOVER_GRANTED = "failover_granted"
    FAILBACK_WAIT_STABLE = "failback_wait_stable"
    FAILBACK_GRANTED = "failback_granted"
    DEVICE_DISABLED = "device_disabled"
    AUTHORITY_FENCED = "authority_fenced"
    AUTHORITY_EXPIRED = "authority_lease_expired"
    REALM_INACTIVE = "realm_inactive"
    MEMBERSHIP_REVOKED = "membership_revoked"
    BINDING_REVOKED = "binding_revoked"
    SNAPSHOT_CLOCK_AHEAD = "snapshot_clock_ahead"
    SNAPSHOT_TOO_OLD = "snapshot_too_old"
    SNAPSHOT_OUT_OF_ORDER = "snapshot_out_of_order"
    SNAPSHOT_SEQUENCE_MISMATCH = "sequence_reuse_mismatch"
    SNAPSHOT_INVALID = "snapshot_invalid"
    DB_UNAVAILABLE = "db_unavailable"
    BOOTSTRAP_NOT_ELIGIBLE = "bootstrap_not_eligible"


class SideEffectPolicy(StrEnum):
    NONE = "none"
    BASELINE = "baseline"
    DESKTOP_CONTINUITY = "desktop_continuity"


class ManagedAuthorityOperation(StrEnum):
    CURRENT_GRANT = "current-grant"
    TRANSITION_CANDIDATE = "transition-candidate"


# Defaults are proposed configuration, not active timers or policy enforcement.
DESKTOP_HEARTBEAT_INTERVAL_SECONDS = 60
DESKTOP_HEARTBEAT_HEALTHY_BEFORE_SECONDS = 90
CLOUD_HEARTBEAT_INTERVAL_SECONDS = 30
DESKTOP_HEARTBEAT_STALE_AFTER_SECONDS = 120
DESKTOP_HEARTBEAT_OFFLINE_AFTER_SECONDS = 300
CLOUD_HEARTBEAT_STALE_AFTER_SECONDS = 60
DESKTOP_SNAPSHOT_STALE_AFTER_SECONDS = 120
CLOUD_SNAPSHOT_STALE_AFTER_SECONDS = 90
SNAPSHOT_STALE_HYSTERESIS_SECONDS = 60
SOURCE_STALE_HYSTERESIS_SECONDS = 60
AUTHORITY_LEASE_TTL_SECONDS = 180
DESKTOP_FAILBACK_MIN_HEARTBEATS = 3
DESKTOP_FAILBACK_STABLE_SECONDS = 120
CANDIDATE_FUTURE_SKEW_SECONDS = 60
CANDIDATE_MAX_AGE_SECONDS = 300

MANAGED_DESKTOP_SNAPSHOT_ENDPOINT = "/api/v1/devices/{device_id}/snapshot"
MANAGED_CLOUD_SNAPSHOT_ENDPOINT = "/api/v1/cloud-bindings/{cloud_binding_id}/snapshot"
AUTHORITY_OPERATION_HEADER = "X-Alertam-Authority-Operation"
AUTHORITY_EPOCH_HEADER = "X-Alertam-Authority-Epoch"
AUTHORITY_LEASE_HEADER = "X-Alertam-Authority-Lease"
SOURCE_INSTANCE_HEADER = "X-Alertam-Source-Instance"


class SourceAuthorityRecord(Contract):
    """Authority is per device_id; never derived from the SessionLease realm_epoch."""

    device_id: str = Field(min_length=1)
    mode: AuthorityMode = AuthorityMode.LEGACY
    active_source: Source | None = None
    authority_epoch: int = Field(default=0, ge=0)
    authority_lease_id: UUID | None = None
    holder_instance_id: UUID | None = None
    lease_expires_at: AwareDatetime | None = None
    granted_at: AwareDatetime | None = None
    last_renewed_at: AwareDatetime | None = None
    last_transition_at: AwareDatetime | None = None
    transition_reason: AuthorityReasonCode | None = None
    cloud_binding_id: UUID | None = None
    realm_id: str | None = Field(default=None, min_length=1)  # Cloud grant association only
    observed_realm_epoch: int | None = Field(default=None, ge=0)  # diagnostics only, NEVER source fencing
    updated_at: AwareDatetime  # server-side record timestamp, future migration 021
    last_authoritative_snapshot_at: AwareDatetime | None = None
    authoritative_snapshot_stale_since: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_grant_state(self) -> "SourceAuthorityRecord":
        grant = (self.active_source, self.authority_lease_id,
                 self.holder_instance_id, self.lease_expires_at)
        if self.mode is AuthorityMode.LEGACY:
            if any(item is not None for item in grant):
                raise ValueError("legacy mode cannot have active managed grant")
        elif any(item is None for item in grant) or self.authority_epoch < 1:
            raise ValueError("managed mode requires an existing source grant")

        cloud_metadata = (self.cloud_binding_id, self.realm_id, self.observed_realm_epoch)
        if self.mode is AuthorityMode.LEGACY or self.active_source is Source.DESKTOP:
            if any(item is not None for item in cloud_metadata):
                raise ValueError("legacy/Desktop authority cannot carry Cloud holder association")
        elif self.active_source is Source.CLOUD:
            if self.cloud_binding_id is None or self.realm_id is None:
                raise ValueError("Cloud authority requires binding and realm for administrative fencing")
        return self


class SourceHeartbeatRecord(Contract):
    device_id: str = Field(min_length=1)
    source: Source
    instance_id: UUID  # process identity; standby has no authority grant
    last_heartbeat_at: AwareDatetime  # server-side receive time
    collection_healthy: bool
    process_healthy: bool = True
    healthy_since: AwareDatetime | None = None
    consecutive_healthy: int = Field(default=0, ge=0)
    last_collection_ok_at: AwareDatetime | None = None
    last_reported_generated_at: AwareDatetime | None = None  # diagnostic only
    last_candidate_generated_at: AwareDatetime | None = None  # standby candidate, not fencing
    last_reason_code: AuthorityReasonCode | None = None
    persistent_state_ready: bool | None = None  # Cloud only
    updated_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_cloud_only_state(self) -> "SourceHeartbeatRecord":
        if self.source is Source.DESKTOP and self.persistent_state_ready is not None:
            raise ValueError("persistent_state_ready is reserved for Cloud heartbeat")
        return self


class ManagedSnapshotCandidate(Contract):
    """Source-only metadata; the PWA MobileSnapshot body is not extended."""

    device_id: str = Field(min_length=1)
    source: Source
    holder_instance_id: UUID
    boot_id: UUID
    sequence: int = Field(gt=0)
    generated_at: AwareDatetime
    snapshot_schema_version: int = Field(ge=1, le=2)
    snapshot: dict[str, Any] = Field(repr=False)

    @model_validator(mode="after")
    def validate_identity(self) -> "ManagedSnapshotCandidate":
        if self.boot_id != self.holder_instance_id:
            raise ValueError("snapshot boot_id must identify holder instance")

        # Duplicate canonical fields must agree with the body that will be persisted.
        # This is contract validation only: the future RPC handles DB arbitration.
        canonical = ("boot_id", "sequence", "schema_version", "generated_at")
        if any(key not in self.snapshot for key in canonical):
            raise ValueError("snapshot canonical metadata missing")

        body_boot_id = self.snapshot["boot_id"]
        if not isinstance(body_boot_id, str):
            raise ValueError("snapshot boot_id must be a UUID string")
        try:
            if UUID(body_boot_id) != self.boot_id:
                raise ValueError("snapshot boot_id mismatch")
        except ValueError as exc:
            raise ValueError("snapshot boot_id mismatch or invalid") from exc

        if type(self.snapshot["sequence"]) is not int or self.snapshot["sequence"] != self.sequence:
            raise ValueError("snapshot sequence mismatch")
        if (type(self.snapshot["schema_version"]) is not int
            or self.snapshot["schema_version"] != self.snapshot_schema_version):
            raise ValueError("snapshot schema_version mismatch")

        body_generated_at = self.snapshot["generated_at"]
        if isinstance(body_generated_at, datetime):
            observed_at = body_generated_at
        elif isinstance(body_generated_at, str):
            try:
                observed_at = datetime.fromisoformat(body_generated_at)
            except ValueError as exc:
                raise ValueError("snapshot generated_at is invalid") from exc
        else:
            raise ValueError("snapshot generated_at must be an ISO datetime")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("snapshot generated_at requires timezone")
        if observed_at.astimezone(timezone.utc) != self.generated_at.astimezone(timezone.utc):
            raise ValueError("snapshot generated_at mismatch")
        return self


class PublishUnderCurrentGrant(Contract):
    """Existing grant write: epoch + lease + instance are mandatory."""

    candidate: ManagedSnapshotCandidate
    authority_epoch: int = Field(gt=0)
    authority_lease_id: UUID
    holder_instance_id: UUID

    @model_validator(mode="after")
    def validate_identity(self) -> "PublishUnderCurrentGrant":
        if self.candidate.holder_instance_id != self.holder_instance_id:
            raise ValueError("writer instance differs from snapshot candidate")
        return self


class TransitionCandidate(Contract):
    """Acquisition request: client MUST NOT supply an authority epoch or lease."""

    candidate: ManagedSnapshotCandidate


class AuthorityGrantView(Contract):
    device_id: str = Field(min_length=1)
    source: Source
    authority_epoch: int = Field(gt=0)
    authority_lease_id: UUID
    holder_instance_id: UUID
    lease_expires_at: AwareDatetime


class ManagedSnapshotAcceptanceResult(Contract):
    """Transactional winner's side-effect instruction; never use a pre-read."""

    status: AuthorityStatus
    device_id: str = Field(min_length=1)
    source: Source
    reason_code: AuthorityReasonCode | None = None
    grant: AuthorityGrantView | None = None
    received_at: AwareDatetime | None = None
    previous_source: Source | None = None
    source_transition: bool = False
    side_effect_policy: SideEffectPolicy = SideEffectPolicy.NONE
    previous_snapshot_for_side_effects: dict[str, Any] | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_side_effect_policy(self) -> "ManagedSnapshotAcceptanceResult":
        if self.status in (AuthorityStatus.ACCEPTED, AuthorityStatus.IDEMPOTENT) and self.grant is None:
            raise ValueError("accepted managed snapshot must return the authoritative grant")
        if self.grant is not None and (
            self.grant.device_id != self.device_id or self.grant.source != self.source
        ):
            raise ValueError("grant device/source mismatch")
        if self.source_transition and (
            self.previous_source is None or self.previous_source == self.source
        ):
            raise ValueError("source transition requires a different previous source")
        if (not self.source_transition and self.previous_source is not None
            and self.previous_source != self.source):
            raise ValueError("different previous source requires committed transition")
        if (self.status in (AuthorityStatus.FENCED, AuthorityStatus.REJECTED, AuthorityStatus.INELIGIBLE)
            and self.source_transition):
            raise ValueError("rejected/losing operation cannot commit a source transition")
        if self.source is Source.CLOUD and self.side_effect_policy is not SideEffectPolicy.NONE:
            raise ValueError("Cloud is state-only")
        if (self.status is AuthorityStatus.ACCEPTED
            and self.source is Source.DESKTOP
            and self.source_transition
            and self.side_effect_policy is not SideEffectPolicy.BASELINE):
            raise ValueError("accepted Desktop source transition must use baseline")
        if self.status is not AuthorityStatus.ACCEPTED:
            if self.side_effect_policy is not SideEffectPolicy.NONE:
                raise ValueError("loser or idempotent retry may not generate side effects")
        if self.side_effect_policy is SideEffectPolicy.DESKTOP_CONTINUITY:
            if (self.source is not Source.DESKTOP
                or self.previous_source is not Source.DESKTOP
                or self.source_transition
                or self.previous_snapshot_for_side_effects is None):
                raise ValueError("desktop continuity requires transactional previous Desktop snapshot")
        elif self.previous_snapshot_for_side_effects is not None:
            raise ValueError("previous snapshot is only allowed for desktop continuity")
        if self.side_effect_policy is SideEffectPolicy.BASELINE and self.source is not Source.DESKTOP:
            raise ValueError("baseline is Desktop-only")
        return self


class AuthorityDecision(Contract):
    device_id: str = Field(min_length=1)
    write_allowed: bool = False
    renew_allowed: bool = False
    reason_code: AuthorityReasonCode | None = None


def _holder_matches(record: SourceAuthorityRecord, command: PublishUnderCurrentGrant) -> bool:
    return (
        record.mode is AuthorityMode.MANAGED
        and record.device_id == command.candidate.device_id
        and record.active_source == command.candidate.source
        and record.authority_epoch == command.authority_epoch
        and record.authority_lease_id == command.authority_lease_id
        and record.holder_instance_id == command.holder_instance_id
    )


def current_grant_write_eligible(
    record: SourceAuthorityRecord,
    command: PublishUnderCurrentGrant,
    *,
    lease_current: bool,
    admin_allowed: bool,
    candidate_valid: bool = True,
) -> AuthorityDecision:
    """Pure precondition, NOT DB arbitration. Snapshot stale is deliberately irrelevant.

    lease_current stands for DB-verified not-expired/not-fenced/not-replaced.
    The future DB must revalidate everything under lock.
    """
    matches = _holder_matches(record, command)
    allowed = matches and lease_current and admin_allowed and candidate_valid
    return AuthorityDecision(
        device_id=command.candidate.device_id, write_allowed=allowed,
        reason_code=None if allowed else AuthorityReasonCode.AUTHORITY_FENCED,
    )


def current_holder_renew_eligible(
    record: SourceAuthorityRecord,
    command: PublishUnderCurrentGrant,
    *,
    lease_current: bool,
    admin_allowed: bool,
    snapshot_fresh: bool,
    holder_healthy: bool = True,
) -> AuthorityDecision:
    """Renew requires authoritative snapshot freshness; recovery writes do not."""
    allowed = (_holder_matches(record, command) and lease_current and admin_allowed
               and snapshot_fresh and holder_healthy)
    return AuthorityDecision(
        device_id=command.candidate.device_id, renew_allowed=allowed,
        reason_code=None if allowed else (
            AuthorityReasonCode.DESKTOP_SNAPSHOT_STALE
            if not snapshot_fresh and record.active_source is Source.DESKTOP
            else AuthorityReasonCode.CLOUD_SNAPSHOT_STALE
            if not snapshot_fresh and record.active_source is Source.CLOUD
            else AuthorityReasonCode.AUTHORITY_FENCED
        ),
    )


def bootstrap_desktop_eligible(
    record: SourceAuthorityRecord,
    first_candidate: ManagedSnapshotCandidate,
    *,
    desktop_healthy: bool,
    desktop_snapshot_fresh: bool,
    boot_matches: bool,
    device_enabled: bool,
) -> bool:
    """C3-B future atomic legacy→managed: first holder MUST be healthy Desktop."""
    return (
        record.mode is AuthorityMode.LEGACY
        and record.active_source is None
        and record.authority_epoch == 0  # initial bootstrap creates epoch 1; reactivation needs separate policy
        and record.device_id == first_candidate.device_id
        and first_candidate.source is Source.DESKTOP
        and desktop_healthy and desktop_snapshot_fresh and boot_matches and device_enabled
    )


class CurrentGrantHeaders(Contract):
    operation: ManagedAuthorityOperation
    authority_epoch: int = Field(gt=0)
    authority_lease_id: UUID
    holder_instance_id: UUID

    @model_validator(mode="after")
    def check_operation(self) -> "CurrentGrantHeaders":
        if self.operation is not ManagedAuthorityOperation.CURRENT_GRANT:
            raise ValueError("incorrect operation for current-grant")
        return self


class TransitionCandidateHeaders(Contract):
    operation: ManagedAuthorityOperation
    holder_instance_id: UUID

    @model_validator(mode="after")
    def check_operation(self) -> "TransitionCandidateHeaders":
        if self.operation is not ManagedAuthorityOperation.TRANSITION_CANDIDATE:
            raise ValueError("incorrect operation for transition candidate")
        return self


def parse_managed_authority_headers(
    headers: Mapping[str, str],
) -> CurrentGrantHeaders | TransitionCandidateHeaders:
    """Shared contract for both Desktop Device and CloudBinding managed endpoints.

    This only validates header shape; it does not authenticate, write or route HTTP.
    """
    canonical = {key.lower(): value for key, value in headers.items()
                 if key.lower().startswith("x-alertam-authority-")
                 or key.lower() == SOURCE_INSTANCE_HEADER.lower()}
    fields = {
        AUTHORITY_OPERATION_HEADER.lower(): "operation",
        AUTHORITY_EPOCH_HEADER.lower(): "authority_epoch",
        AUTHORITY_LEASE_HEADER.lower(): "authority_lease_id",
        SOURCE_INSTANCE_HEADER.lower(): "holder_instance_id",
    }
    values = {fields.get(k, k): v for k, v in canonical.items()}
    if values.get("operation") == ManagedAuthorityOperation.CURRENT_GRANT:
        return CurrentGrantHeaders.model_validate(values)
    # unknown operation is rejected by literal enum validation, even without extra fields
    return TransitionCandidateHeaders.model_validate(values)
