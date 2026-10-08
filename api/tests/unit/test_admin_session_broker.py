from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.repositories.cloud_bindings import WebPilotAuthRealmRecord
from app.repositories.devices import DeviceAuthRecord
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.session_broker import (
    ProviderScopeProfile,
    ScopeStatus,
)
from scripts.admin_session_broker import (
    configure_required_scope,
    verify_publisher_scope,
)


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
PUB = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_admin_configures_required_scope_and_reclassifies_publisher():
    repo = MemoryDeviceRepository(clock=lambda: NOW)
    repo.put_device(DeviceAuthRecord("pecem-01", "hash", enabled=True))
    repo.put_webpilot_auth_realm(
        WebPilotAuthRealmRecord(
            realm_id="webpilot-pecem",
            active=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repo.authorize_realm_device("webpilot-pecem", "pecem-01")

    required = configure_required_scope(
        repo,
        "webpilot-pecem",
        ProviderScopeProfile("pecem-standard", 1, ("maneuvers", "weather")),
    )
    assert required.profile.scope_id == "pecem-standard"

    publisher = repo.ensure_session_publisher(
        device_id="pecem-01",
        realm_id="webpilot-pecem",
        publisher_id=PUB,
        provider_scope=ProviderScopeProfile(
            "pecem-standard",
            1,
            ("maneuvers", "weather"),
        ),
    )
    assert publisher is not None
    assert publisher.scope_status is ScopeStatus.UNVERIFIED

    verified = verify_publisher_scope(repo, PUB)
    assert verified.scope_status is ScopeStatus.VERIFIED


def test_admin_device_compensation_probes_session_publishers():
    from scripts.admin_device import _DEPENDENCY_PROBES

    assert ("webpilot_session_publishers", "device_id") in _DEPENDENCY_PROBES
