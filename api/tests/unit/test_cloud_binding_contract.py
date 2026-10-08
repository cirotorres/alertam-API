from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.repositories.cloud_bindings import (
    CloudBindingRecord,
    CloudBindingStatus,
    CloudBindingsRepository,
    RealmDeviceAuthorizationRecord,
    WebPilotAuthRealmRecord,
)


NOW = datetime(2026, 10, 8, 5, 30, tzinfo=timezone.utc)


def test_domain_records_expose_only_c1_identity_and_authority_fields():
    assert {field.name for field in fields(WebPilotAuthRealmRecord)} == {
        "realm_id",
        "active",
        "created_at",
        "updated_at",
    }
    assert {field.name for field in fields(RealmDeviceAuthorizationRecord)} == {
        "realm_id",
        "device_id",
        "authorized_at",
        "revoked_at",
    }
    assert {field.name for field in fields(CloudBindingRecord)} == {
        "cloud_binding_id",
        "device_id",
        "realm_id",
        "credential_hash",
        "credential_version",
        "status",
        "created_at",
        "updated_at",
        "revoked_at",
    }


def test_cloud_binding_record_hides_credential_hash_from_repr():
    record = CloudBindingRecord(
        cloud_binding_id=UUID("11111111-1111-1111-1111-111111111111"),
        device_id="pecem-01",
        realm_id="webpilot-pecem",
        credential_hash="cloud-credential-hash-must-not-leak",
        credential_version=1,
        status=CloudBindingStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
        revoked_at=None,
    )

    rendered = repr(record)

    assert "cloud-credential-hash-must-not-leak" not in rendered
    assert record.status is CloudBindingStatus.ACTIVE


@pytest.mark.parametrize(
    ("status", "version", "revoked_at"),
    [
        (CloudBindingStatus.ACTIVE, 0, None),
        (CloudBindingStatus.ACTIVE, 1, NOW),
        (CloudBindingStatus.REVOKED, 1, None),
    ],
)
def test_cloud_binding_record_rejects_invalid_lifecycle_state(
    status,
    version,
    revoked_at,
):
    with pytest.raises(ValueError):
        CloudBindingRecord(
            cloud_binding_id=UUID("22222222-2222-2222-2222-222222222222"),
            device_id="pecem-01",
            realm_id="webpilot-pecem",
            credential_hash="hash",
            credential_version=version,
            status=status,
            created_at=NOW,
            updated_at=NOW,
            revoked_at=revoked_at,
        )


def test_realm_device_authorization_active_reflects_revocation_state():
    active = RealmDeviceAuthorizationRecord(
        realm_id="webpilot-pecem",
        device_id="pecem-01",
        authorized_at=NOW,
        revoked_at=None,
    )
    revoked = RealmDeviceAuthorizationRecord(
        realm_id="webpilot-pecem",
        device_id="pecem-02",
        authorized_at=NOW,
        revoked_at=NOW,
    )

    assert active.active is True
    assert revoked.active is False


def test_cloud_binding_repository_protocol_is_limited_to_c1_contract():
    public_methods = {
        name
        for name, value in vars(CloudBindingsRepository).items()
        if callable(value) and not name.startswith("_")
    }

    assert public_methods == {
        "get_webpilot_auth_realm",
        "authorize_realm_device",
        "get_realm_device_authorization",
        "get_active_cloud_binding",
        "list_cloud_bindings",
        "ensure_cloud_binding",
        "rotate_cloud_binding",
        "revoke_cloud_binding",
    }

    lowered = " ".join(public_methods).lower()
    assert "session" not in lowered
    assert "lease" not in lowered
    assert "source" not in lowered
