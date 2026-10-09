from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.source_authority import (
    AuthorityDecision,
    AuthorityGrantView,
    AuthorityMode,
    AuthorityReasonCode,
    AuthorityStatus,
    ManagedAuthorityOperation,
    ManagedSnapshotAcceptanceResult,
    ManagedSnapshotCandidate,
    PublishUnderCurrentGrant,
    SideEffectPolicy,
    Source,
    SourceAuthorityRecord,
    SourceHeartbeatRecord,
    TransitionCandidate,
    bootstrap_desktop_eligible,
    current_grant_write_eligible,
    current_holder_renew_eligible,
    parse_managed_authority_headers,
)
from app.repositories.source_authority import SourceAuthorityRepository


NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
BOOT = UUID("11111111-1111-4111-8111-111111111111")
LEASE = UUID("22222222-2222-4222-8222-222222222222")


def candidate(source=Source.DESKTOP, device_id="device-a"):
    return ManagedSnapshotCandidate(
        device_id=device_id, source=source, holder_instance_id=BOOT,
        boot_id=BOOT, sequence=3, generated_at=NOW,
        snapshot_schema_version=2, snapshot={
            "schema_version": 2, "boot_id": str(BOOT),
            "sequence": 3, "generated_at": NOW.isoformat(),
        },
    )


def grant(source=Source.DESKTOP, device_id="device-a"):
    cloud_assoc = (
        {"cloud_binding_id": UUID("66666666-6666-4666-8666-666666666666"), "realm_id": "realm-a"}
        if source is Source.CLOUD else {}
    )
    return SourceAuthorityRecord(
        device_id=device_id, mode=AuthorityMode.MANAGED, active_source=source,
        authority_epoch=7, authority_lease_id=LEASE,
        holder_instance_id=BOOT, lease_expires_at=NOW + timedelta(seconds=30),
        last_authoritative_snapshot_at=NOW - timedelta(seconds=140),
        authoritative_snapshot_stale_since=NOW - timedelta(seconds=20),
        updated_at=NOW,
        **cloud_assoc,
    )


def publish(source=Source.DESKTOP, device_id="device-a"):
    return PublishUnderCurrentGrant(
        candidate=candidate(source, device_id), authority_epoch=7,
        authority_lease_id=LEASE, holder_instance_id=BOOT,
    )


def test_source_and_mode_are_closed_contracts():
    assert {item.value for item in Source} == {"desktop", "cloud"}
    assert {item.value for item in AuthorityMode} == {"legacy", "managed"}
    assert SourceAuthorityRecord(device_id="device-a", updated_at=NOW).mode is AuthorityMode.LEGACY
    assert AuthorityReasonCode.DESKTOP_SNAPSHOT_STALE.value == "desktop_snapshot_stale"
    assert AuthorityStatus.ACCEPTED.value == "accepted"


def test_realm_epoch_is_not_accepted_as_source_epoch():
    with pytest.raises(ValidationError):
        PublishUnderCurrentGrant.model_validate({
            "candidate": candidate(), "realm_epoch": 7,
            "authority_lease_id": LEASE, "holder_instance_id": BOOT,
        })


def test_current_grant_command_requires_all_fencing_fields():
    for field in ("authority_epoch", "authority_lease_id", "holder_instance_id"):
        invalid = publish().model_dump()
        invalid.pop(field)
        with pytest.raises(ValidationError):
            PublishUnderCurrentGrant.model_validate(invalid)
    assert publish().authority_epoch == 7


def test_transition_candidate_forbids_client_supplied_future_grant():
    assert TransitionCandidate(candidate=candidate()).candidate.sequence == 3
    for field, value in (("authority_epoch", 8), ("authority_lease_id", LEASE)):
        with pytest.raises(ValidationError):
            TransitionCandidate.model_validate({"candidate": candidate(), field: value})


def test_candidate_boot_must_match_writer_instance():
    with pytest.raises(ValidationError):
        ManagedSnapshotCandidate.model_validate({
            **candidate().model_dump(), "boot_id": UUID("33333333-3333-4333-8333-333333333333")
        })


def test_cross_device_grant_cannot_write_or_renew():
    assert not current_grant_write_eligible(grant(), publish(device_id="device-b"),
                                            lease_current=True, admin_allowed=True).write_allowed
    assert not current_holder_renew_eligible(grant(), publish(device_id="device-b"),
                                              lease_current=True, admin_allowed=True,
                                              snapshot_fresh=True).renew_allowed


def test_stale_snapshot_can_be_write_eligible_but_not_renew_eligible():
    current = grant()
    write = current_grant_write_eligible(current, publish(), lease_current=True, admin_allowed=True)
    renew = current_holder_renew_eligible(current, publish(), lease_current=True,
                                          admin_allowed=True, snapshot_fresh=False)
    assert isinstance(write, AuthorityDecision)
    assert write.write_allowed
    assert not renew.renew_allowed


@pytest.mark.parametrize("source", [Source.DESKTOP, Source.CLOUD])
def test_recovery_possible_for_both_sources_before_grant_expiry(source):
    current = grant(source)
    command = publish(source)
    assert current_grant_write_eligible(current, command, lease_current=True,
                                        admin_allowed=True).write_allowed
    assert not current_holder_renew_eligible(current, command, lease_current=True,
                                             admin_allowed=True, snapshot_fresh=False).renew_allowed


@pytest.mark.parametrize(("lease_current", "admin_allowed"), [(False, True), (True, False)])
def test_expired_or_fenced_grant_cannot_recover(lease_current, admin_allowed):
    assert not current_grant_write_eligible(grant(), publish(), lease_current=lease_current,
                                            admin_allowed=admin_allowed).write_allowed


def test_grant_cannot_be_used_with_different_epoch_lease_or_instance():
    for replacement in (
        {"authority_epoch": 8},
        {"authority_lease_id": UUID("44444444-4444-4444-8444-444444444444")},
        {"holder_instance_id": UUID("55555555-5555-4555-8555-555555555555")},
    ):
        command = publish().model_copy(update=replacement)
        assert not current_grant_write_eligible(grant(), command, lease_current=True,
                                                admin_allowed=True).write_allowed


def test_bootstrap_requires_healthy_fresh_desktop_and_matching_boot():
    current = SourceAuthorityRecord(device_id="device-a", updated_at=NOW)
    assert bootstrap_desktop_eligible(current, candidate(), desktop_healthy=True,
                                      desktop_snapshot_fresh=True, boot_matches=True,
                                      device_enabled=True)
    for change in (
        {"desktop_healthy": False}, {"desktop_snapshot_fresh": False},
        {"boot_matches": False}, {"device_enabled": False},
    ):
        flags = dict(desktop_healthy=True, desktop_snapshot_fresh=True,
                     boot_matches=True, device_enabled=True)
        flags.update(change)
        assert not bootstrap_desktop_eligible(current, candidate(), **flags)
    assert not bootstrap_desktop_eligible(current, candidate(Source.CLOUD),
                                         desktop_healthy=True, desktop_snapshot_fresh=True,
                                         boot_matches=True, device_enabled=True)


def test_managed_authority_cannot_exist_without_first_grant():
    with pytest.raises(ValidationError):
        SourceAuthorityRecord(device_id="device-a", updated_at=NOW, mode=AuthorityMode.MANAGED)


def test_side_effects_contract_rejects_cloud_and_requires_desktop_continuity():
    accepted = dict(
        status=AuthorityStatus.ACCEPTED, device_id="device-a",
        grant=AuthorityGrantView(
            device_id="device-a", source=Source.DESKTOP, authority_epoch=7,
            authority_lease_id=LEASE, holder_instance_id=BOOT,
            lease_expires_at=NOW + timedelta(seconds=30),
        ),
    )
    baseline = ManagedSnapshotAcceptanceResult(**accepted, source=Source.DESKTOP,
                                                 previous_source=Source.CLOUD,
                                                 source_transition=True,
                                                 side_effect_policy=SideEffectPolicy.BASELINE)
    assert baseline.side_effect_policy != SideEffectPolicy.DESKTOP_CONTINUITY
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(**accepted, source=Source.CLOUD,
                                        previous_source=Source.DESKTOP,
                                        source_transition=True,
                                        side_effect_policy=SideEffectPolicy.DESKTOP_CONTINUITY,
                                        previous_snapshot_for_side_effects=candidate().snapshot)
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(**accepted, source=Source.DESKTOP,
                                        previous_source=Source.CLOUD,
                                        source_transition=True,
                                        side_effect_policy=SideEffectPolicy.DESKTOP_CONTINUITY,
                                        previous_snapshot_for_side_effects=candidate().snapshot)
    continuity = ManagedSnapshotAcceptanceResult(
        **accepted, source=Source.DESKTOP, previous_source=Source.DESKTOP,
        source_transition=False, side_effect_policy=SideEffectPolicy.DESKTOP_CONTINUITY,
        previous_snapshot_for_side_effects=candidate().snapshot,
    )
    assert continuity.previous_snapshot_for_side_effects is not None
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(**accepted, source=Source.DESKTOP,
                                        previous_source=Source.DESKTOP,
                                        source_transition=False,
                                        side_effect_policy=SideEffectPolicy.BASELINE,
                                        previous_snapshot_for_side_effects=candidate().snapshot)


def test_rejected_write_never_authorizes_side_effects():
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(status=AuthorityStatus.FENCED,
                                        device_id="device-a", source=Source.DESKTOP,
                                        side_effect_policy=SideEffectPolicy.BASELINE)


def test_metadata_is_device_scoped_and_no_credentials_are_fields():
    heartbeat = SourceHeartbeatRecord(
        device_id="device-a", source=Source.DESKTOP, instance_id=BOOT,
        last_heartbeat_at=NOW, collection_healthy=True,
    )
    assert heartbeat.device_id == "device-a"
    assert AuthorityGrantView(
        device_id="device-a", source=Source.DESKTOP, authority_epoch=7,
        authority_lease_id=LEASE, holder_instance_id=BOOT,
        lease_expires_at=NOW + timedelta(seconds=30),
    ).authority_epoch == 7
    assert not {"cookies", "secret", "realm_epoch"}.intersection(
        ManagedSnapshotCandidate.model_fields | SourceAuthorityRecord.model_fields
    )
    assert hasattr(SourceAuthorityRepository, "accept_current_grant_snapshot")
    assert hasattr(SourceAuthorityRepository, "accept_transition_candidate")


def test_managed_header_operation_is_shared_and_mode_specific():
    assert parse_managed_authority_headers({
        "X-Alertam-Authority-Operation": "current-grant",
        "X-Alertam-Authority-Epoch": "7",
        "X-Alertam-Authority-Lease": str(LEASE),
        "X-Alertam-Source-Instance": str(BOOT),
    }).operation is ManagedAuthorityOperation.CURRENT_GRANT
    transition = parse_managed_authority_headers({
        "X-Alertam-Authority-Operation": "transition-candidate",
        "X-Alertam-Source-Instance": str(BOOT),
    })
    assert transition.operation is ManagedAuthorityOperation.TRANSITION_CANDIDATE
    with pytest.raises(ValidationError):
        parse_managed_authority_headers({
            "X-Alertam-Authority-Operation": "transition-candidate",
            "X-Alertam-Authority-Epoch": "8",
            "X-Alertam-Source-Instance": str(BOOT),
        })

def test_accepted_managed_result_returns_grant_and_blocks_cross_device_grant():
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(
            status=AuthorityStatus.ACCEPTED, device_id="device-a",
            source=Source.DESKTOP,
        )
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(
            status=AuthorityStatus.ACCEPTED, device_id="device-a",
            source=Source.DESKTOP,
            grant=AuthorityGrantView(
                device_id="device-b", source=Source.DESKTOP, authority_epoch=7,
                authority_lease_id=LEASE, holder_instance_id=BOOT,
                lease_expires_at=NOW + timedelta(seconds=30),
            ),
        )


def test_repository_command_types_cannot_be_confused():
    from typing import get_type_hints

    current_annotations = get_type_hints(SourceAuthorityRepository.accept_current_grant_snapshot)
    transition_annotations = get_type_hints(SourceAuthorityRepository.accept_transition_candidate)
    assert current_annotations["command"] is PublishUnderCurrentGrant
    assert transition_annotations["command"] is TransitionCandidate
    assert "authority_epoch" not in TransitionCandidate.model_fields
    assert "authority_lease_id" not in TransitionCandidate.model_fields


def test_realm_epoch_forbidden_in_source_authority():
    with pytest.raises(ValidationError):
        SourceAuthorityRecord.model_validate({
            "device_id": "device-a", "realm_epoch": 99,
        })

def test_idempotent_replay_can_return_grant_but_never_side_effects():
    saved_grant = AuthorityGrantView(
        device_id="device-a", source=Source.DESKTOP, authority_epoch=7,
        authority_lease_id=LEASE, holder_instance_id=BOOT,
        lease_expires_at=NOW + timedelta(seconds=30),
    )
    assert ManagedSnapshotAcceptanceResult(
        status=AuthorityStatus.IDEMPOTENT, device_id="device-a",
        source=Source.DESKTOP, grant=saved_grant,
    ).side_effect_policy is SideEffectPolicy.NONE
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(
            status=AuthorityStatus.IDEMPOTENT, device_id="device-a",
            source=Source.DESKTOP, grant=saved_grant,
            side_effect_policy=SideEffectPolicy.BASELINE,
        )


# R10-F1..F5 — RED regressions from the independent review.

@pytest.mark.parametrize("headers", [
    {"X-Alertam-Source-Instance": str(BOOT)},
    {"X-Alertam-Authority-Operation": "unknown", "X-Alertam-Source-Instance": str(BOOT)},
    {"X-Alertam-Authority-Operation": "current-grant", "X-Alertam-Source-Instance": str(BOOT)},
    {"X-Alertam-Authority-Operation": "transition-candidate"},
    {"X-Alertam-Authority-Operation": "transition-candidate",
     "X-Alertam-Source-Instance": str(BOOT), "X-Alertam-Authority-Lease": str(LEASE)},
])
def test_r10_f1_operation_header_is_required_and_modes_are_exclusive(headers):
    with pytest.raises(ValidationError):
        parse_managed_authority_headers(headers)


@pytest.mark.parametrize("source", [Source.DESKTOP, Source.CLOUD])
def test_r10_f2_standby_heartbeat_is_instance_not_holder(source):
    heartbeat = SourceHeartbeatRecord(
        device_id="device-a", source=source, instance_id=BOOT,
        last_heartbeat_at=NOW, collection_healthy=True,
    )
    assert heartbeat.instance_id == BOOT
    assert "holder_instance_id" not in SourceHeartbeatRecord.model_fields
    assert "authority_epoch" not in SourceHeartbeatRecord.model_fields
    assert "authority_lease_id" not in SourceHeartbeatRecord.model_fields


@pytest.mark.parametrize("side_effect_policy", [
    SideEffectPolicy.NONE, SideEffectPolicy.DESKTOP_CONTINUITY,
])
def test_r10_f3_desktop_transition_requires_baseline(side_effect_policy):
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(
            status=AuthorityStatus.ACCEPTED,
            device_id="device-a", source=Source.DESKTOP,
            previous_source=Source.CLOUD, source_transition=True,
            side_effect_policy=side_effect_policy,
            grant=AuthorityGrantView(
                device_id="device-a", source=Source.DESKTOP, authority_epoch=7,
                authority_lease_id=LEASE, holder_instance_id=BOOT,
                lease_expires_at=NOW + timedelta(seconds=30),
            ),
        )


def test_r10_f3_cloud_acceptance_is_state_only_even_with_transition():
    result = ManagedSnapshotAcceptanceResult(
        status=AuthorityStatus.ACCEPTED, device_id="device-a",
        source=Source.CLOUD, previous_source=Source.DESKTOP,
        source_transition=True, side_effect_policy=SideEffectPolicy.NONE,
        grant=AuthorityGrantView(
            device_id="device-a", source=Source.CLOUD, authority_epoch=7,
            authority_lease_id=LEASE, holder_instance_id=BOOT,
            lease_expires_at=NOW + timedelta(seconds=30),
        ),
    )
    assert result.side_effect_policy is SideEffectPolicy.NONE


def test_r10_f4_source_reason_code_is_distinct_from_legacy_accept_status():
    from app.repositories.devices import AcceptSnapshotStatus

    assert AuthorityReasonCode.SNAPSHOT_OUT_OF_ORDER.value == "snapshot_out_of_order"
    assert AcceptSnapshotStatus.OUT_OF_ORDER.value == "out_of_order"


def _r10_candidate_data():
    return {
        "device_id": "device-a",
        "source": Source.DESKTOP,
        "holder_instance_id": BOOT,
        "boot_id": BOOT,
        "sequence": 3,
        "generated_at": NOW,
        "snapshot_schema_version": 2,
        "snapshot": {
            "schema_version": 2,
            "boot_id": str(BOOT),
            "sequence": 3,
            "generated_at": NOW.isoformat(),
        },
    }


@pytest.mark.parametrize(("key", "replacement"), [
    ("boot_id", "33333333-3333-4333-8333-333333333333"),
    ("sequence", 4),
    ("schema_version", 1),
    ("generated_at", "2026-10-09T11:00:00Z"),
])
def test_r10_f5_rejects_mismatching_duplicate_snapshot_metadata(key, replacement):
    data = _r10_candidate_data()
    data["snapshot"][key] = replacement
    with pytest.raises(ValidationError):
        ManagedSnapshotCandidate.model_validate(data)


@pytest.mark.parametrize("key", ["boot_id", "sequence", "schema_version", "generated_at"])
def test_r10_f5_all_canonical_body_fields_are_required(key):
    data = _r10_candidate_data()
    del data["snapshot"][key]
    with pytest.raises(ValidationError):
        ManagedSnapshotCandidate.model_validate(data)


@pytest.mark.parametrize("date_value", [
    "2026-10-09T12:00:00", "invalid-date", 1791547200,
])
def test_r10_f5_body_generated_at_must_be_timezone_aware(date_value):
    data = _r10_candidate_data()
    data["snapshot"]["generated_at"] = date_value
    with pytest.raises(ValidationError):
        ManagedSnapshotCandidate.model_validate(data)


def test_r10_f5_same_instant_different_timezone_is_valid():
    data = _r10_candidate_data()
    data["snapshot"]["generated_at"] = "2026-10-09T09:00:00-03:00"
    result = ManagedSnapshotCandidate.model_validate(data)
    assert result.generated_at == NOW


# R10.1 — independent reviewer findings, RED first.
BINDING = UUID("66666666-6666-4666-8666-666666666666")


def _r101_authority(source=Source.CLOUD, **overrides):
    data = dict(
        device_id="device-a", mode=AuthorityMode.MANAGED, active_source=source,
        authority_epoch=7, authority_lease_id=LEASE,
        holder_instance_id=BOOT, lease_expires_at=NOW + timedelta(seconds=30),
        updated_at=NOW,
    )
    if source is Source.CLOUD:
        data.update(cloud_binding_id=BINDING, realm_id="realm-a")
    data.update(overrides)
    return data


@pytest.mark.parametrize("missing", ["cloud_binding_id", "realm_id"])
def test_r101_f1_cloud_grant_requires_both_admin_fencing_associations(missing):
    data = _r101_authority()
    data.pop(missing)
    with pytest.raises(ValidationError):
        SourceAuthorityRecord.model_validate(data)


@pytest.mark.parametrize(("field", "value"), [
    ("cloud_binding_id", BINDING),
    ("realm_id", "realm-a"),
    ("observed_realm_epoch", 14),
])
def test_r101_f1_desktop_grant_rejects_cloud_metadata(field, value):
    with pytest.raises(ValidationError):
        SourceAuthorityRecord.model_validate(_r101_authority(Source.DESKTOP, **{field: value}))


@pytest.mark.parametrize(("field", "value"), [
    ("cloud_binding_id", BINDING),
    ("realm_id", "realm-a"),
    ("observed_realm_epoch", 14),
])
def test_r101_f1_legacy_has_no_active_cloud_holder_association(field, value):
    with pytest.raises(ValidationError):
        SourceAuthorityRecord.model_validate({
            "device_id": "device-a", "updated_at": NOW, field: value,
        })


def test_r101_f1_observed_realm_epoch_is_diagnostic_not_authority_fencing():
    current = SourceAuthorityRecord.model_validate(_r101_authority(observed_realm_epoch=5))
    newer_observation = SourceAuthorityRecord.model_validate(
        _r101_authority(observed_realm_epoch=6)
    )
    assert current.observed_realm_epoch == 5
    assert current.updated_at == NOW
    assert current_holder_renew_eligible(
        current, publish(Source.CLOUD), lease_current=True,
        admin_allowed=True, snapshot_fresh=True,
    ).renew_allowed
    for record in (current, newer_observation):
        assert current_grant_write_eligible(
            record, publish(Source.CLOUD), lease_current=True,
            admin_allowed=True,
        ).write_allowed


def test_r101_f1_updated_at_is_timezone_aware_and_present():
    assert SourceAuthorityRecord.model_validate(
        _r101_authority(updated_at=NOW)
    ).updated_at == NOW
    for bad in (None, datetime(2026, 10, 9, 12)):
        with pytest.raises(ValidationError):
            SourceAuthorityRecord.model_validate(_r101_authority(updated_at=bad))


def test_r101_f1_cloud_grant_allows_no_observed_realm_epoch():
    assert SourceAuthorityRecord.model_validate(
        _r101_authority()
    ).observed_realm_epoch is None


def test_r101_f1_heartbeat_persistent_state_ready_only_cloud():
    for val in (True, False):
        with pytest.raises(ValidationError):
            SourceHeartbeatRecord(
                device_id="device-a", source=Source.DESKTOP, instance_id=BOOT,
                last_heartbeat_at=NOW, collection_healthy=True,
                persistent_state_ready=val,
            )
        cloud = SourceHeartbeatRecord(
            device_id="device-a", source=Source.CLOUD, instance_id=BOOT,
            last_heartbeat_at=NOW, collection_healthy=True,
            persistent_state_ready=val,
        )
        assert cloud.persistent_state_ready is val
    desktop = SourceHeartbeatRecord(
        device_id="device-a", source=Source.DESKTOP, instance_id=BOOT,
        last_heartbeat_at=NOW, collection_healthy=True,
    )
    assert desktop.persistent_state_ready is None


def _r101_result(status=AuthorityStatus.ACCEPTED, source=Source.DESKTOP, **kwargs):
    fields = dict(
        status=status, device_id="device-a", source=source,
        side_effect_policy=SideEffectPolicy.NONE,
    )
    if status in (AuthorityStatus.ACCEPTED, AuthorityStatus.IDEMPOTENT):
        fields["grant"] = AuthorityGrantView(
            device_id="device-a", source=source, authority_epoch=7,
            authority_lease_id=LEASE, holder_instance_id=BOOT,
            lease_expires_at=NOW + timedelta(seconds=30),
        )
    fields.update(kwargs)
    return fields


def test_r101_f2_accepted_different_previous_source_requires_transition():
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(**_r101_result(
            previous_source=Source.CLOUD, source_transition=False,
        ))


@pytest.mark.parametrize("status", [
    AuthorityStatus.FENCED, AuthorityStatus.REJECTED, AuthorityStatus.INELIGIBLE,
])
def test_r101_f2_loser_cannot_claim_committed_transition(status):
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(**_r101_result(
            status=status, previous_source=Source.CLOUD,
            source_transition=True,
        ))


def test_r101_f2_idempotent_result_may_describe_old_transition_with_no_side_effect():
    result = ManagedSnapshotAcceptanceResult(**_r101_result(
        status=AuthorityStatus.IDEMPOTENT, previous_source=Source.CLOUD,
        source_transition=True,
    ))
    assert result.source_transition
    assert result.side_effect_policy is SideEffectPolicy.NONE
    with pytest.raises(ValidationError):
        ManagedSnapshotAcceptanceResult(**_r101_result(
            status=AuthorityStatus.IDEMPOTENT, previous_source=Source.CLOUD,
            source_transition=True, side_effect_policy=SideEffectPolicy.BASELINE,
        ))


def test_r101_f2_accepted_same_source_continuity_and_cloud_transition_remain_valid():
    continuity = ManagedSnapshotAcceptanceResult(**_r101_result(
        previous_source=Source.DESKTOP, source_transition=False,
        side_effect_policy=SideEffectPolicy.DESKTOP_CONTINUITY,
        previous_snapshot_for_side_effects=candidate().snapshot,
    ))
    assert continuity.side_effect_policy is SideEffectPolicy.DESKTOP_CONTINUITY
    accepted_cloud = ManagedSnapshotAcceptanceResult(**_r101_result(
        source=Source.CLOUD, previous_source=Source.DESKTOP,
        source_transition=True, side_effect_policy=SideEffectPolicy.NONE,
    ))
    assert accepted_cloud.side_effect_policy is SideEffectPolicy.NONE
