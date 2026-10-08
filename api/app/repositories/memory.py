from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Callable, Iterable
from uuid import UUID, uuid4

from app.models.maneuver_event import ManeuverEventIn
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.cloud_bindings import (
    CloudBindingAuthorityRecord,
    CloudBindingConflictError,
    CloudBindingRecord,
    CloudBindingStatus,
    RealmDeviceAuthorizationRecord,
    WebPilotAuthRealmRecord,
)
from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    MobileInstallationDisplayCodeConflictError,
    MobileInstallationRecord,
    MobileInstallationSwitchConflictError,
    MobilePairingCodeConflictError,
    MobilePairingCodeRedeemResult,
    MobilePairingCodeRedeemStatus,
    SnapshotCandidate,
    StoredSnapshot,
)
from app.repositories.events import (
    AcceptEventResult,
    AcceptEventStatus,
    EventPage,
    ManeuverEventDetail,
    PushDelivery,
    PushDeliveryStatus,
    PushInstallation,
    PushPreferences,
    StoredManeuverEvent,
)
from app.repositories.session_broker import (
    EncryptedSessionLeaseRecord,
    ProviderScopeProfile,
    RequiredProviderScopeRecord,
    ScopeStatus,
    SessionLeaseGenerationConflictError,
    SessionLeaseReplayError,
    SessionLeaseStatus,
    SessionPublisherConflictError,
    SessionPublisherRecord,
    SessionPublisherStatus,
)
from app.repositories.tracking import (
    AcceptTrackingEventResult,
    AcceptTrackingEventStatus,
    InstallationTrackingEventRecord,
    StoredVesselTrackingEvent,
    TrackedVesselRecord,
    TrackingPushDelivery,
    TrackingPushDeliveryStatus,
    VesselEventRecord,
    VesselEvidence,
)


DeviceRecord = DeviceAuthRecord


class MemoryDeviceRepository:
    """Repository efêmero para desenvolvimento e testes sem Supabase."""

    def __init__(
        self,
        *,
        devices: Iterable[DeviceAuthRecord] = (),
        snapshots: Iterable[StoredSnapshot] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._devices = {item.device_id: item for item in devices}
        self._snapshots = {item.device_id: item for item in snapshots}
        self._webpilot_auth_realms: dict[str, WebPilotAuthRealmRecord] = {}
        self._realm_device_authorizations: dict[
            tuple[str, str], RealmDeviceAuthorizationRecord
        ] = {}
        self._cloud_bindings: dict[UUID, CloudBindingRecord] = {}
        self._required_provider_scopes: dict[str, RequiredProviderScopeRecord] = {}
        self._session_publishers: dict[UUID, SessionPublisherRecord] = {}
        self._session_leases: dict[UUID, EncryptedSessionLeaseRecord] = {}
        self._session_lease_by_generation: dict[tuple[UUID, int], UUID] = {}
        self._realm_epoch_counters: dict[str, int] = {}
        self._events_by_id: dict[str, StoredManeuverEvent] = {}
        self._event_ingestion_sequence = 0
        self._tracking_events_by_id: dict[str, StoredVesselTrackingEvent] = {}
        self._tracking_event_ingestion_sequence = 0
        self._mobile_installations: dict[UUID, MobileInstallationRecord] = {}
        self._mobile_session_switches: dict[
            UUID, tuple[str, UUID, str, UUID, str]
        ] = {}
        self._mobile_pairing_codes: dict[str, dict[str, object]] = {}
        self._mobile_pairing_failures: dict[datetime, int] = {}
        self._tracked_vessels: dict[UUID, TrackedVesselRecord] = {}
        self._push_installations: dict[object, PushInstallation] = {}
        self._push_deliveries: dict[tuple[str, object], PushDelivery] = {}
        self._tracking_push_deliveries: dict[
            tuple[str, object], TrackingPushDelivery
        ] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = Lock()

    def create_device(self, record: DeviceAuthRecord) -> None:
        if record.device_id in self._devices:
            raise DeviceAlreadyExistsError(record.device_id)
        self._devices[record.device_id] = record

    def put_device(self, record: DeviceAuthRecord) -> None:
        self._devices[record.device_id] = record

    def get_device_auth(self, device_id: str) -> DeviceAuthRecord | None:
        return self._devices.get(device_id)

    def ensure_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None:
        with self._lock:
            current = self._webpilot_auth_realms.get(realm_id)
            if current is not None:
                return current
            now = self._clock()
            current = WebPilotAuthRealmRecord(
                realm_id=realm_id,
                active=True,
                created_at=now,
                updated_at=now,
            )
            self._webpilot_auth_realms[realm_id] = current
            return current

    def put_webpilot_auth_realm(
        self,
        record: WebPilotAuthRealmRecord,
    ) -> None:
        with self._lock:
            self._webpilot_auth_realms[record.realm_id] = record

    def get_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None:
        with self._lock:
            return self._webpilot_auth_realms.get(realm_id)

    def authorize_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        with self._lock:
            if (
                realm_id not in self._webpilot_auth_realms
                or device_id not in self._devices
            ):
                return None
            key = (realm_id, device_id)
            current = self._realm_device_authorizations.get(key)
            if current is not None and current.active:
                return current
            authorized = RealmDeviceAuthorizationRecord(
                realm_id=realm_id,
                device_id=device_id,
                authorized_at=self._clock(),
                revoked_at=None,
            )
            self._realm_device_authorizations[key] = authorized
            return authorized

    def revoke_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        with self._lock:
            key = (realm_id, device_id)
            current = self._realm_device_authorizations.get(key)
            if current is None or current.revoked_at is not None:
                return current
            revoked = replace(current, revoked_at=self._clock())
            self._realm_device_authorizations[key] = revoked
            return revoked

    def set_webpilot_auth_realm_active(
        self,
        realm_id: str,
        active: bool,
    ) -> WebPilotAuthRealmRecord | None:
        with self._lock:
            current = self._webpilot_auth_realms.get(realm_id)
            if current is None:
                return None
            if current.active is active:
                return current
            updated = replace(
                current,
                active=active,
                updated_at=self._clock(),
            )
            self._webpilot_auth_realms[realm_id] = updated
            return updated

    def get_realm_device_authorization(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        with self._lock:
            return self._realm_device_authorizations.get((realm_id, device_id))

    def set_required_provider_scope(
        self,
        realm_id: str,
        profile: ProviderScopeProfile,
    ) -> RequiredProviderScopeRecord | None:
        with self._lock:
            if realm_id not in self._webpilot_auth_realms:
                return None
            record = RequiredProviderScopeRecord(
                realm_id=realm_id,
                profile=profile,
                updated_at=self._clock(),
            )
            self._required_provider_scopes[realm_id] = record
            return record

    def get_required_provider_scope(
        self,
        realm_id: str,
    ) -> RequiredProviderScopeRecord | None:
        with self._lock:
            return self._required_provider_scopes.get(realm_id)

    def ensure_session_publisher(
        self,
        *,
        device_id: str,
        realm_id: str,
        publisher_id: UUID,
        provider_scope: ProviderScopeProfile,
    ) -> SessionPublisherRecord | None:
        with self._lock:
            if not self._binding_authority_active_unlocked(device_id, realm_id):
                return None
            now = self._clock()
            current = self._session_publishers.get(publisher_id)
            if current is not None:
                if current.device_id != device_id or current.realm_id != realm_id:
                    raise SessionPublisherConflictError()
                if current.status is SessionPublisherStatus.REVOKED:
                    raise SessionPublisherConflictError()
                if current.provider_scope == provider_scope:
                    return current
                updated = replace(
                    current,
                    provider_scope=provider_scope,
                    scope_status=ScopeStatus.UNVERIFIED,
                    scope_verified_at=None,
                    updated_at=now,
                )
                self._session_publishers[publisher_id] = updated
                return updated

            for existing_id, existing in tuple(self._session_publishers.items()):
                if (
                    existing.device_id == device_id
                    and existing.realm_id == realm_id
                    and existing.status is SessionPublisherStatus.ACTIVE
                ):
                    self._session_publishers[existing_id] = replace(
                        existing,
                        status=SessionPublisherStatus.REVOKED,
                        revoked_at=now,
                        updated_at=now,
                    )

            publisher = SessionPublisherRecord(
                publisher_id=publisher_id,
                realm_id=realm_id,
                device_id=device_id,
                provider_scope=provider_scope,
                scope_status=ScopeStatus.UNVERIFIED,
                scope_verified_at=None,
                last_generation=0,
                status=SessionPublisherStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                revoked_at=None,
            )
            self._session_publishers[publisher_id] = publisher
            return publisher

    def get_session_publisher(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None:
        with self._lock:
            return self._session_publishers.get(publisher_id)

    def verify_session_publisher_scope(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None:
        with self._lock:
            publisher = self._session_publishers.get(publisher_id)
            if publisher is None or publisher.status is SessionPublisherStatus.REVOKED:
                return publisher
            required = self._required_provider_scopes.get(publisher.realm_id)
            status = (
                ScopeStatus.VERIFIED
                if required is not None and required.profile == publisher.provider_scope
                else ScopeStatus.INCOMPATIBLE
            )
            now = self._clock()
            updated = replace(
                publisher,
                scope_status=status,
                scope_verified_at=now if status is ScopeStatus.VERIFIED else None,
                updated_at=now,
            )
            self._session_publishers[publisher_id] = updated
            return updated

    def revoke_session_publisher(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None:
        with self._lock:
            publisher = self._session_publishers.get(publisher_id)
            if publisher is None or publisher.status is SessionPublisherStatus.REVOKED:
                return publisher
            now = self._clock()
            revoked = replace(
                publisher,
                status=SessionPublisherStatus.REVOKED,
                revoked_at=now,
                updated_at=now,
            )
            self._session_publishers[publisher_id] = revoked
            return revoked

    def _publisher_eligible_unlocked(
        self,
        publisher: SessionPublisherRecord,
    ) -> bool:
        required = self._required_provider_scopes.get(publisher.realm_id)
        return bool(
            publisher.status is SessionPublisherStatus.ACTIVE
            and publisher.scope_status is ScopeStatus.VERIFIED
            and required is not None
            and required.profile == publisher.provider_scope
            and self._binding_authority_active_unlocked(
                publisher.device_id,
                publisher.realm_id,
            )
        )

    def accept_session_lease_atomic(
        self,
        *,
        device_id: str,
        realm_id: str,
        publisher_id: UUID,
        lease_id: UUID,
        local_generation: int,
        payload_fingerprint: str,
        ciphertext: str,
        nonce: str,
        key_version: int,
        payload_schema_version: int,
        expires_at: datetime | None,
    ) -> EncryptedSessionLeaseRecord | None:
        with self._lock:
            publisher = self._session_publishers.get(publisher_id)
            if (
                publisher is None
                or publisher.device_id != device_id
                or publisher.realm_id != realm_id
                or not self._publisher_eligible_unlocked(publisher)
            ):
                return None

            generation_key = (publisher_id, local_generation)
            existing_id = self._session_lease_by_generation.get(generation_key)
            if existing_id is not None:
                existing = self._session_leases[existing_id]
                if existing.status is not SessionLeaseStatus.ACCEPTED:
                    raise SessionLeaseReplayError()
                if existing.payload_fingerprint != payload_fingerprint:
                    raise SessionLeaseGenerationConflictError()
                return existing

            if local_generation <= publisher.last_generation:
                raise SessionLeaseReplayError()

            next_epoch = self._realm_epoch_counters.get(realm_id, 0) + 1
            self._realm_epoch_counters[realm_id] = next_epoch
            now = self._clock()
            lease = EncryptedSessionLeaseRecord(
                lease_id=lease_id,
                realm_id=realm_id,
                publisher_id=publisher_id,
                local_generation=local_generation,
                realm_epoch=next_epoch,
                payload_fingerprint=payload_fingerprint,
                ciphertext=ciphertext,
                nonce=nonce,
                key_version=key_version,
                payload_schema_version=payload_schema_version,
                received_at=now,
                expires_at=expires_at,
                status=SessionLeaseStatus.ACCEPTED,
            )
            self._session_leases[lease_id] = lease
            self._session_lease_by_generation[generation_key] = lease_id
            self._session_publishers[publisher_id] = replace(
                publisher,
                last_generation=local_generation,
                updated_at=now,
            )
            return lease

    def get_session_lease(
        self,
        lease_id: UUID,
    ) -> EncryptedSessionLeaseRecord | None:
        with self._lock:
            return self._session_leases.get(lease_id)

    def get_current_session_lease(
        self,
        realm_id: str,
        *,
        now: datetime,
    ) -> EncryptedSessionLeaseRecord | None:
        with self._lock:
            candidates: list[EncryptedSessionLeaseRecord] = []
            for lease in self._session_leases.values():
                if (
                    lease.realm_id != realm_id
                    or lease.status is not SessionLeaseStatus.ACCEPTED
                    or (lease.expires_at is not None and lease.expires_at <= now)
                ):
                    continue
                publisher = self._session_publishers.get(lease.publisher_id)
                if publisher is not None and self._publisher_eligible_unlocked(publisher):
                    candidates.append(lease)
            if not candidates:
                return None
            return max(candidates, key=lambda item: item.realm_epoch)

    def revoke_session_lease(
        self,
        *,
        device_id: str,
        realm_id: str,
        lease_id: UUID,
    ) -> EncryptedSessionLeaseRecord | None:
        with self._lock:
            lease = self._session_leases.get(lease_id)
            if lease is None or lease.realm_id != realm_id:
                return None
            publisher = self._session_publishers.get(lease.publisher_id)
            if (
                publisher is None
                or publisher.device_id != device_id
                or not self._binding_authority_active_unlocked(device_id, realm_id)
            ):
                return None
            if lease.status is not SessionLeaseStatus.ACCEPTED:
                return lease
            revoked = replace(
                lease,
                status=SessionLeaseStatus.REVOKED,
                revoked_at=self._clock(),
            )
            self._session_leases[lease_id] = revoked
            return revoked

    def invalidate_session_lease(
        self,
        *,
        realm_id: str,
        lease_id: UUID,
        realm_epoch: int,
    ) -> EncryptedSessionLeaseRecord | None:
        with self._lock:
            lease = self._session_leases.get(lease_id)
            if (
                lease is None
                or lease.realm_id != realm_id
                or lease.realm_epoch != realm_epoch
            ):
                return None
            if lease.status is not SessionLeaseStatus.ACCEPTED:
                return lease
            invalidated = replace(
                lease,
                status=SessionLeaseStatus.INVALIDATED,
                invalidated_at=self._clock(),
            )
            self._session_leases[lease_id] = invalidated
            return invalidated

    def _binding_authority_active_unlocked(
        self,
        device_id: str,
        realm_id: str,
    ) -> bool:
        device = self._devices.get(device_id)
        realm = self._webpilot_auth_realms.get(realm_id)
        authorization = self._realm_device_authorizations.get(
            (realm_id, device_id)
        )
        return bool(
            device is not None
            and device.enabled
            and realm is not None
            and realm.active
            and authorization is not None
            and authorization.active
        )

    def _get_active_cloud_binding_unlocked(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        for binding in self._cloud_bindings.values():
            if (
                binding.device_id == device_id
                and binding.status is CloudBindingStatus.ACTIVE
            ):
                return binding
        return None

    def get_cloud_binding_authority(
        self,
        cloud_binding_id: UUID,
    ) -> CloudBindingAuthorityRecord | None:
        with self._lock:
            binding = self._cloud_bindings.get(cloud_binding_id)
            if binding is None:
                return None
            device = self._devices.get(binding.device_id)
            realm = self._webpilot_auth_realms.get(binding.realm_id)
            membership = self._realm_device_authorizations.get(
                (binding.realm_id, binding.device_id)
            )
            return CloudBindingAuthorityRecord(
                cloud_binding_id=binding.cloud_binding_id,
                device_id=binding.device_id,
                realm_id=binding.realm_id,
                credential_hash=binding.credential_hash,
                status=binding.status,
                device_enabled=bool(device and device.enabled),
                realm_active=bool(realm and realm.active),
                membership_active=bool(membership and membership.active),
            )

    def get_active_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        with self._lock:
            return self._get_active_cloud_binding_unlocked(device_id)

    def list_cloud_bindings(
        self,
        device_id: str,
    ) -> tuple[CloudBindingRecord, ...]:
        with self._lock:
            bindings = [
                binding
                for binding in self._cloud_bindings.values()
                if binding.device_id == device_id
            ]
            return tuple(bindings)

    def ensure_cloud_binding(
        self,
        device_id: str,
        realm_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None:
        with self._lock:
            if not self._binding_authority_active_unlocked(
                device_id,
                realm_id,
            ):
                return None

            current = self._get_active_cloud_binding_unlocked(device_id)
            if current is not None:
                if (
                    current.realm_id == realm_id
                    and current.credential_hash == credential_hash
                ):
                    return current
                raise CloudBindingConflictError(device_id)

            now = self._clock()
            binding = CloudBindingRecord(
                cloud_binding_id=uuid4(),
                device_id=device_id,
                realm_id=realm_id,
                credential_hash=credential_hash,
                credential_version=1,
                status=CloudBindingStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                revoked_at=None,
            )
            self._cloud_bindings[binding.cloud_binding_id] = binding
            return binding

    def rotate_cloud_binding(
        self,
        device_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None:
        with self._lock:
            current = self._get_active_cloud_binding_unlocked(device_id)
            if current is None or not self._binding_authority_active_unlocked(
                device_id,
                current.realm_id,
            ):
                return None
            if current.credential_hash == credential_hash:
                return current

            rotated = replace(
                current,
                credential_hash=credential_hash,
                credential_version=current.credential_version + 1,
                updated_at=self._clock(),
            )
            self._cloud_bindings[current.cloud_binding_id] = rotated
            return rotated

    def revoke_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        with self._lock:
            current = self._get_active_cloud_binding_unlocked(device_id)
            if current is None:
                previous = [
                    binding
                    for binding in self._cloud_bindings.values()
                    if binding.device_id == device_id
                ]
                if not previous:
                    return None
                latest = previous[-1]
                if not self._binding_authority_active_unlocked(
                    device_id,
                    latest.realm_id,
                ):
                    return None
                return latest

            if not self._binding_authority_active_unlocked(
                device_id,
                current.realm_id,
            ):
                return None

            now = self._clock()
            revoked = replace(
                current,
                status=CloudBindingStatus.REVOKED,
                updated_at=now,
                revoked_at=now,
            )
            self._cloud_bindings[current.cloud_binding_id] = revoked
            return revoked

    def ensure_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str = "other",
        display_code: str | None = None,
    ) -> MobileInstallationRecord | None:
        with self._lock:
            if device_id not in self._devices:
                return None
            now = self._clock()
            current = self._mobile_installations.get(installation_id)
            if current is not None and (
                current.device_id != device_id or not current.active
            ):
                return None
            if current is None:
                if display_code and any(
                    item.display_code == display_code
                    for item in self._mobile_installations.values()
                ):
                    raise MobileInstallationDisplayCodeConflictError(
                        display_code
                    )
                current = MobileInstallationRecord(
                    installation_id=installation_id,
                    device_id=device_id,
                    active=True,
                    created_at=now,
                    last_seen_at=now,
                    revoked_at=None,
                    platform=platform,
                    display_code=display_code or "",
                )
            else:
                current = replace(
                    current,
                    last_seen_at=now,
                )
            self._mobile_installations[installation_id] = current
            return current

    def get_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> MobileInstallationRecord | None:
        current = self._mobile_installations.get(installation_id)
        if current is None or current.device_id != device_id:
            return None
        return current

    def list_mobile_installations(
        self,
        device_id: str,
        *,
        revoked_since: datetime,
    ) -> tuple[MobileInstallationRecord, ...]:
        items = [
            item
            for item in self._mobile_installations.values()
            if item.device_id == device_id
            and (
                item.active
                or (
                    item.revoked_at is not None
                    and item.revoked_at >= revoked_since
                )
            )
        ]
        items.sort(key=lambda item: (item.created_at, str(item.installation_id)))
        return tuple(items)

    def touch_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str,
    ) -> MobileInstallationRecord | None:
        with self._lock:
            current = self._mobile_installations.get(installation_id)
            if (
                current is None
                or current.device_id != device_id
                or not current.active
            ):
                return None
            next_platform = (
                platform
                if current.platform == "other" and platform != "other"
                else current.platform
            )
            updated = replace(
                current,
                last_seen_at=self._clock(),
                platform=next_platform,
            )
            self._mobile_installations[installation_id] = updated
            return updated

    def revoke_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool:
        with self._lock:
            current = self._mobile_installations.get(installation_id)
            if current is None or current.device_id != device_id:
                return False
            if not current.active:
                return True
            now = self._clock()
            self._mobile_installations[installation_id] = replace(
                current,
                active=False,
                last_seen_at=now,
                revoked_at=now,
            )
            for tracked_id, tracked in tuple(self._tracked_vessels.items()):
                if tracked.installation_id != installation_id or not tracked.active:
                    continue
                self._tracked_vessels[tracked_id] = replace(
                    tracked,
                    active=False,
                    stopped_at=now,
                )
            push = self._push_installations.get(installation_id)
            if push is not None and push.device_id == device_id:
                self._push_installations[installation_id] = replace(
                    push,
                    endpoint=None,
                    p256dh=None,
                    auth=None,
                    active=False,
                    last_seen_at=now,
                    updated_at=now,
                )
            return True

    def switch_mobile_installation(
        self,
        from_device_id: str,
        from_installation_id: UUID,
        to_device_id: str,
        to_installation_id: UUID,
        *,
        platform: str,
        display_code: str,
        switch_id: UUID,
    ) -> MobileInstallationRecord | None:
        with self._lock:
            payload = (
                from_device_id,
                from_installation_id,
                to_device_id,
                to_installation_id,
                platform,
            )
            previous = self._mobile_session_switches.get(switch_id)
            if previous is not None:
                if previous != payload:
                    raise MobileInstallationSwitchConflictError()
                target = self._mobile_installations.get(to_installation_id)
                if (
                    target is None
                    or target.device_id != to_device_id
                    or not target.active
                ):
                    return None
                return target

            if from_device_id == to_device_id:
                raise MobileInstallationSwitchConflictError()

            source = self._mobile_installations.get(from_installation_id)
            if (
                source is None
                or source.device_id != from_device_id
                or not source.active
                or to_device_id not in self._devices
            ):
                return None

            if to_installation_id in self._mobile_installations:
                raise MobileInstallationSwitchConflictError()

            if any(
                item.display_code == display_code
                for item in self._mobile_installations.values()
            ):
                raise MobileInstallationDisplayCodeConflictError(display_code)

            now = self._clock()
            target = MobileInstallationRecord(
                installation_id=to_installation_id,
                device_id=to_device_id,
                active=True,
                created_at=now,
                last_seen_at=now,
                revoked_at=None,
                platform=platform,
                display_code=display_code,
            )
            source_revoked = replace(
                source,
                active=False,
                last_seen_at=now,
                revoked_at=source.revoked_at or now,
            )
            tracked_updates = {
                tracked_id: replace(
                    tracked,
                    active=False,
                    stopped_at=tracked.stopped_at or now,
                )
                for tracked_id, tracked in self._tracked_vessels.items()
                if (
                    tracked.installation_id == from_installation_id
                    and tracked.device_id == from_device_id
                    and tracked.active
                )
            }
            push = self._push_installations.get(from_installation_id)
            push_revoked = None
            if push is not None and push.device_id == from_device_id:
                push_revoked = replace(
                    push,
                    endpoint=None,
                    p256dh=None,
                    auth=None,
                    active=False,
                    last_seen_at=now,
                    updated_at=now,
                )

            self._mobile_installations[to_installation_id] = target
            self._mobile_installations[from_installation_id] = source_revoked
            self._tracked_vessels.update(tracked_updates)
            if push_revoked is not None:
                self._push_installations[from_installation_id] = push_revoked
            self._mobile_session_switches[switch_id] = payload
            return target

    def get_snapshot(self, device_id: str) -> StoredSnapshot | None:
        return self._snapshots.get(device_id)

    def put_snapshot(self, snapshot: StoredSnapshot) -> None:
        self._snapshots[snapshot.device_id] = snapshot

    def replace_mobile_pairing_code(
        self,
        device_id: str,
        code_hash: str,
        *,
        expires_at: datetime,
    ) -> bool:
        with self._lock:
            if device_id not in self._devices:
                return False
            if any(
                item.get("code_hash") == code_hash and other_id != device_id
                for other_id, item in self._mobile_pairing_codes.items()
            ):
                raise MobilePairingCodeConflictError()
            self._mobile_pairing_codes[device_id] = {
                "code_hash": code_hash,
                "expires_at": expires_at,
                "redeemed_at": None,
                "ticket_hash": None,
                "ticket_expires_at": None,
                "consumed_at": None,
                "consumed_for": None,
            }
            return True

    def redeem_mobile_pairing_code(
        self,
        code_hash: str,
        ticket_hash: str,
        *,
        ticket_expires_at: datetime,
        now: datetime,
    ) -> MobilePairingCodeRedeemResult:
        with self._lock:
            window = now.replace(second=0, microsecond=0)
            failures = self._mobile_pairing_failures.get(window, 0)
            if failures >= 30:
                return MobilePairingCodeRedeemResult(
                    MobilePairingCodeRedeemStatus.RATE_LIMITED
                )

            for device_id, item in self._mobile_pairing_codes.items():
                if (
                    item.get("code_hash") == code_hash
                    and item.get("redeemed_at") is None
                    and isinstance(item.get("expires_at"), datetime)
                    and item["expires_at"] > now
                ):
                    item["redeemed_at"] = now
                    item["ticket_hash"] = ticket_hash
                    item["ticket_expires_at"] = ticket_expires_at
                    return MobilePairingCodeRedeemResult(
                        MobilePairingCodeRedeemStatus.OK,
                        device_id=device_id,
                        ticket_expires_at=ticket_expires_at,
                    )

            self._mobile_pairing_failures[window] = failures + 1
            return MobilePairingCodeRedeemResult(
                MobilePairingCodeRedeemStatus.INVALID
            )

    def validate_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        *,
        now: datetime,
    ) -> bool:
        with self._lock:
            item = self._mobile_pairing_codes.get(device_id)
            return bool(
                item
                and item.get("ticket_hash") == ticket_hash
                and item.get("redeemed_at") is not None
                and isinstance(item.get("ticket_expires_at"), datetime)
                and item["ticket_expires_at"] > now
            )

    def consume_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        purpose: str,
        *,
        now: datetime,
    ) -> bool:
        with self._lock:
            item = self._mobile_pairing_codes.get(device_id)
            if not (
                item
                and item.get("ticket_hash") == ticket_hash
                and item.get("redeemed_at") is not None
                and isinstance(item.get("ticket_expires_at"), datetime)
                and item["ticket_expires_at"] > now
            ):
                return False
            consumed_for = item.get("consumed_for")
            if consumed_for is not None:
                return consumed_for == purpose
            item["consumed_at"] = now
            item["consumed_for"] = purpose
            return True

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool:
        with self._lock:
            current = self._devices.get(device_id)
            if current is None:
                return False
            self._devices[device_id] = replace(
                current,
                view_secret_hash=view_secret_hash,
            )
            now = self._clock()
            for installation_id, installation in tuple(
                self._mobile_installations.items()
            ):
                if (
                    installation.device_id != device_id
                    or not installation.active
                ):
                    continue
                self._mobile_installations[installation_id] = replace(
                    installation,
                    active=False,
                    last_seen_at=now,
                    revoked_at=now,
                )
            for tracked_id, tracked in tuple(
                self._tracked_vessels.items()
            ):
                if tracked.device_id != device_id or not tracked.active:
                    continue
                self._tracked_vessels[tracked_id] = replace(
                    tracked,
                    active=False,
                    stopped_at=now,
                )
            for installation_id, installation in tuple(
                self._push_installations.items()
            ):
                if installation.device_id != device_id:
                    continue
                self._push_installations[installation_id] = replace(
                    installation,
                    endpoint=None,
                    p256dh=None,
                    auth=None,
                    active=False,
                    last_seen_at=now,
                    updated_at=now,
                )
            return True

    def accept_snapshot_atomic(
        self,
        candidate: SnapshotCandidate,
    ) -> AcceptSnapshotResult:
        with self._lock:
            if candidate.device_id not in self._devices:
                return AcceptSnapshotResult(
                    status=AcceptSnapshotStatus.DEVICE_NOT_FOUND,
                )

            current = self._snapshots.get(candidate.device_id)
            if current is not None and current.boot_id == candidate.boot_id:
                if candidate.sequence < current.sequence:
                    return AcceptSnapshotResult(
                        status=AcceptSnapshotStatus.OUT_OF_ORDER,
                        received_at=current.received_at,
                    )
                if candidate.sequence == current.sequence:
                    if current.snapshot == candidate.snapshot:
                        return AcceptSnapshotResult(
                            status=AcceptSnapshotStatus.IDEMPOTENT,
                            received_at=current.received_at,
                        )
                    return AcceptSnapshotResult(
                        status=AcceptSnapshotStatus.SEQUENCE_REUSE_MISMATCH,
                        received_at=current.received_at,
                    )

            received_at = self._clock()
            self._snapshots[candidate.device_id] = StoredSnapshot(
                device_id=candidate.device_id,
                snapshot=candidate.snapshot,
                snapshot_schema_version=candidate.snapshot_schema_version,
                boot_id=candidate.boot_id,
                sequence=candidate.sequence,
                generated_at=candidate.generated_at,
                received_at=received_at,
            )
            return AcceptSnapshotResult(
                status=AcceptSnapshotStatus.ACCEPTED,
                received_at=received_at,
            )

    def accept_maneuver_event_atomic(
        self,
        device_id: str,
        event: ManeuverEventIn,
    ) -> AcceptEventResult:
        with self._lock:
            if device_id not in self._devices:
                return AcceptEventResult(AcceptEventStatus.DEVICE_NOT_FOUND)

            event_id = str(event.event_id)
            existing = self._events_by_id.get(event_id)
            if existing is not None:
                same = (
                    existing.device_id == device_id
                    and existing.event.canonical_payload()
                    == event.canonical_payload()
                )
                return AcceptEventResult(
                    AcceptEventStatus.IDEMPOTENT
                    if same
                    else AcceptEventStatus.PAYLOAD_MISMATCH,
                    existing,
                )

            self._event_ingestion_sequence += 1
            stored = StoredManeuverEvent(
                ingestion_id=self._event_ingestion_sequence,
                device_id=device_id,
                event=event,
                ingested_at=self._clock(),
            )
            self._events_by_id[event_id] = stored
            return AcceptEventResult(AcceptEventStatus.ACCEPTED, stored)

    @staticmethod
    def _normalized_vessel_name(value: str) -> str:
        return " ".join(value.upper().split())

    @classmethod
    def _same_vessel(
        cls,
        requested_imo: str | None,
        requested_name: str,
        candidate_imo: str | None,
        candidate_name: str,
    ) -> bool:
        if requested_imo:
            return (
                candidate_imo is not None
                and candidate_imo.strip() == requested_imo.strip()
            )
        return cls._normalized_vessel_name(candidate_name) == (
            cls._normalized_vessel_name(requested_name)
        )

    def find_vessel_evidence(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
    ) -> VesselEvidence | None:
        snapshot = self._snapshots.get(device_id)
        if snapshot is not None:
            vessels = snapshot.snapshot.get("vessels", [])
            if isinstance(vessels, list):
                for raw in vessels:
                    if not isinstance(raw, dict):
                        continue
                    name = str(raw.get("name", ""))
                    imo = raw.get("imo")
                    candidate_imo = None if imo is None else str(imo)
                    if not self._same_vessel(
                        vessel_imo, vessel_name, candidate_imo, name
                    ):
                        continue
                    identity = (
                        f"IMO:{candidate_imo}"
                        if candidate_imo
                        else f"NAME:{self._normalized_vessel_name(name)}"
                    )
                    return VesselEvidence(
                        vessel_identity=identity,
                        vessel_imo=candidate_imo,
                        vessel_name=name,
                        current={
                            "present": True,
                            "status": raw.get("status"),
                            "section": raw.get("section"),
                            "berth": raw.get("berth"),
                            "side": raw.get("side"),
                            "eta": raw.get("eta"),
                            "etb_ets": raw.get("etb_ets"),
                            "pob": raw.get("pob"),
                            "pob_at": None,
                        },
                        observed_at=snapshot.generated_at,
                    )

        tracking = sorted(
            (
                item
                for item in self._tracking_events_by_id.values()
                if item.device_id == device_id
                and self._same_vessel(
                    vessel_imo,
                    vessel_name,
                    item.event.vessel_imo,
                    item.event.vessel_name,
                )
            ),
            key=lambda item: item.ingestion_id,
            reverse=True,
        )
        if tracking:
            item = tracking[0]
            return VesselEvidence(
                vessel_identity=item.event.vessel_identity,
                vessel_imo=item.event.vessel_imo,
                vessel_name=item.event.vessel_name,
                current=item.event.current.model_dump(mode="json"),
                observed_at=item.event.occurred_at,
            )

        maneuvers = sorted(
            (
                item
                for item in self._events_by_id.values()
                if item.device_id == device_id
                and self._same_vessel(
                    vessel_imo,
                    vessel_name,
                    item.event.vessel_imo,
                    item.event.vessel_name,
                )
            ),
            key=lambda item: item.ingestion_id,
            reverse=True,
        )
        if maneuvers:
            item = maneuvers[0]
            event = item.event
            return VesselEvidence(
                vessel_identity=event.vessel_identity,
                vessel_imo=event.vessel_imo,
                vessel_name=event.vessel_name,
                current={
                    "present": None,
                    "status": None,
                    "section": None,
                    "berth": event.berth,
                    "side": None,
                    "eta": None,
                    "etb_ets": None,
                    "pob": event.pob,
                    "pob_at": (
                        None
                        if event.pob_at is None
                        else event.pob_at.isoformat()
                    ),
                },
                observed_at=event.occurred_at,
            )
        return None

    def upsert_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        evidence: VesselEvidence,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            installation = self._mobile_installations.get(installation_id)
            if (
                installation is None
                or installation.device_id != device_id
                or not installation.active
            ):
                return None
            existing = None
            for item in self._tracked_vessels.values():
                if (
                    item.device_id != device_id
                    or item.installation_id != installation_id
                ):
                    continue
                if item.vessel_identity == evidence.vessel_identity:
                    existing = item
                    break
                if (
                    evidence.vessel_imo
                    and item.vessel_imo is None
                    and self._normalized_vessel_name(item.vessel_name)
                    == self._normalized_vessel_name(evidence.vessel_name)
                ):
                    existing = item
                    break
            now = self._clock()
            if existing is None:
                record = TrackedVesselRecord(
                    tracked_vessel_id=uuid4(),
                    device_id=device_id,
                    installation_id=installation_id,
                    vessel_identity=evidence.vessel_identity,
                    vessel_imo=evidence.vessel_imo,
                    vessel_name=evidence.vessel_name,
                    started_at=now,
                    active=True,
                    stopped_at=None,
                    last_seen_at=evidence.observed_at,
                    current=evidence.current,
                )
            else:
                record = replace(
                    existing,
                    vessel_identity=evidence.vessel_identity,
                    vessel_imo=evidence.vessel_imo,
                    vessel_name=evidence.vessel_name,
                    started_at=(
                        existing.started_at if existing.active else now
                    ),
                    active=True,
                    stopped_at=None,
                    last_seen_at=evidence.observed_at,
                    current=evidence.current,
                )
            self._tracked_vessels[record.tracked_vessel_id] = record
            return record

    def list_tracked_vessels(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> tuple[TrackedVesselRecord, ...]:
        with self._lock:
            return tuple(sorted(
                (
                    item for item in self._tracked_vessels.values()
                    if item.device_id == device_id
                    and item.installation_id == installation_id
                    and item.active
                ),
                key=lambda item: item.started_at,
            ))

    def get_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            item = self._tracked_vessels.get(tracked_vessel_id)
            if (
                item is None
                or item.device_id != device_id
                or item.installation_id != installation_id
            ):
                return None
            return item

    def deactivate_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            item = self._tracked_vessels.get(tracked_vessel_id)
            if (
                item is None
                or item.device_id != device_id
                or item.installation_id != installation_id
            ):
                return None
            if item.active:
                item = replace(
                    item,
                    active=False,
                    stopped_at=self._clock(),
                )
                self._tracked_vessels[tracked_vessel_id] = item
            return item

    @classmethod
    def _tracked_record_matches_vessel(
        cls,
        tracked: TrackedVesselRecord,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
    ) -> bool:
        if tracked.vessel_identity == vessel_identity:
            return True
        if vessel_imo is not None:
            if tracked.vessel_imo == vessel_imo:
                return True
            if (
                tracked.vessel_imo is None
                and cls._normalized_vessel_name(tracked.vessel_name)
                == cls._normalized_vessel_name(vessel_name)
            ):
                return True
            return False
        return (
            tracked.vessel_imo is None
            and cls._normalized_vessel_name(tracked.vessel_name)
            == cls._normalized_vessel_name(vessel_name)
        )

    @staticmethod
    def _empty_tracking_current() -> dict[str, object | None]:
        return {
            "present": None,
            "status": None,
            "section": None,
            "berth": None,
            "side": None,
            "eta": None,
            "etb_ets": None,
            "pob": None,
            "pob_at": None,
        }

    def project_tracked_vessels(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
        observed_at: datetime,
        replace_current: bool,
        current: dict[str, object] | None = None,
        patch: dict[str, object] | None = None,
    ) -> int:
        with self._lock:
            updated = 0
            for tracked_id, tracked in tuple(self._tracked_vessels.items()):
                if tracked.device_id != device_id or not tracked.active:
                    continue
                if not self._tracked_record_matches_vessel(
                    tracked,
                    vessel_identity=vessel_identity,
                    vessel_imo=vessel_imo,
                    vessel_name=vessel_name,
                ):
                    continue
                if (
                    tracked.last_seen_at is not None
                    and observed_at < tracked.last_seen_at
                ):
                    continue

                if replace_current:
                    next_current = (
                        None if current is None else dict(current)
                    )
                else:
                    next_current = dict(
                        tracked.current or self._empty_tracking_current()
                    )
                    if patch:
                        next_current.update(patch)

                promoted_identity = tracked.vessel_identity
                promoted_imo = tracked.vessel_imo
                promoted_name = tracked.vessel_name
                if vessel_imo is not None:
                    promoted_identity = vessel_identity
                    promoted_imo = vessel_imo
                    promoted_name = vessel_name

                self._tracked_vessels[tracked_id] = replace(
                    tracked,
                    vessel_identity=promoted_identity,
                    vessel_imo=promoted_imo,
                    vessel_name=promoted_name,
                    last_seen_at=observed_at,
                    current=next_current,
                )
                updated += 1
            return updated

    def list_tracked_vessel_event_records(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> tuple[VesselEventRecord, ...]:
        with self._lock:
            tracked = self._tracked_vessels.get(tracked_vessel_id)
            if (
                tracked is None
                or tracked.device_id != device_id
                or tracked.installation_id != installation_id
            ):
                return ()

            records: list[VesselEventRecord] = []
            for stored in self._events_by_id.values():
                event = stored.event
                if stored.device_id != device_id:
                    continue
                if not self._tracked_record_matches_vessel(
                    tracked,
                    vessel_identity=event.vessel_identity,
                    vessel_imo=event.vessel_imo,
                    vessel_name=event.vessel_name,
                ):
                    continue
                records.append(VesselEventRecord(
                    kind="MANEUVER",
                    ingestion_id=stored.ingestion_id,
                    ingested_at=stored.ingested_at,
                    event=event,
                ))
            for stored in self._tracking_events_by_id.values():
                event = stored.event
                if stored.device_id != device_id:
                    continue
                if not self._tracked_record_matches_vessel(
                    tracked,
                    vessel_identity=event.vessel_identity,
                    vessel_imo=event.vessel_imo,
                    vessel_name=event.vessel_name,
                ):
                    continue
                records.append(VesselEventRecord(
                    kind="TRACKING",
                    ingestion_id=stored.ingestion_id,
                    ingested_at=stored.ingested_at,
                    event=event,
                ))
            return tuple(records)

    def latest_tracking_event_cursor(
        self,
        device_id: str,
    ) -> int | None:
        with self._lock:
            values = [
                stored.ingestion_id
                for stored in self._tracking_events_by_id.values()
                if stored.device_id == device_id
            ]
            return max(values) if values else None

    def list_installation_tracking_events(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        after: int,
        limit: int,
    ) -> tuple[InstallationTrackingEventRecord, ...]:
        with self._lock:
            active_trackings = tuple(
                tracked
                for tracked in self._tracked_vessels.values()
                if tracked.device_id == device_id
                and tracked.installation_id == installation_id
                and tracked.active
            )
            result: list[InstallationTrackingEventRecord] = []
            ordered = sorted(
                (
                    stored
                    for stored in self._tracking_events_by_id.values()
                    if stored.device_id == device_id
                    and stored.ingestion_id > after
                ),
                key=lambda stored: stored.ingestion_id,
            )
            for stored in ordered:
                event = stored.event
                for tracked in active_trackings:
                    if event.occurred_at < tracked.started_at:
                        continue
                    if not self._tracked_record_matches_vessel(
                        tracked,
                        vessel_identity=event.vessel_identity,
                        vessel_imo=event.vessel_imo,
                        vessel_name=event.vessel_name,
                    ):
                        continue
                    result.append(InstallationTrackingEventRecord(
                        tracked_vessel_id=tracked.tracked_vessel_id,
                        stored=stored,
                    ))
                    break
                if len(result) >= limit:
                    break
            return tuple(result)

    def find_active_tracked_vessel_for_event(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
        occurred_at: datetime,
    ) -> TrackedVesselRecord | None:
        with self._lock:
            for tracked in self._tracked_vessels.values():
                if (
                    tracked.device_id != device_id
                    or tracked.installation_id != installation_id
                    or not tracked.active
                    or tracked.started_at > occurred_at
                ):
                    continue
                if self._tracked_record_matches_vessel(
                    tracked,
                    vessel_identity=vessel_identity,
                    vessel_imo=vessel_imo,
                    vessel_name=vessel_name,
                ):
                    return tracked
            return None

    def accept_vessel_tracking_event_atomic(
        self,
        device_id: str,
        event: VesselTrackingEventIn,
    ) -> AcceptTrackingEventResult:
        with self._lock:
            if device_id not in self._devices:
                return AcceptTrackingEventResult(
                    AcceptTrackingEventStatus.DEVICE_NOT_FOUND
                )

            event_id = str(event.event_id)
            existing = self._tracking_events_by_id.get(event_id)
            if existing is not None:
                same = (
                    existing.device_id == device_id
                    and existing.event.canonical_payload()
                    == event.canonical_payload()
                )
                return AcceptTrackingEventResult(
                    AcceptTrackingEventStatus.IDEMPOTENT
                    if same
                    else AcceptTrackingEventStatus.PAYLOAD_MISMATCH,
                    existing,
                )

            self._tracking_event_ingestion_sequence += 1
            stored = StoredVesselTrackingEvent(
                ingestion_id=self._tracking_event_ingestion_sequence,
                device_id=device_id,
                event=event,
                ingested_at=self._clock(),
            )
            self._tracking_events_by_id[event_id] = stored
            return AcceptTrackingEventResult(
                AcceptTrackingEventStatus.ACCEPTED,
                stored,
            )

    def list_maneuver_events(
        self,
        device_id: str,
        *,
        after: int | None = None,
        before: int | None = None,
        limit: int = 50,
    ) -> EventPage:
        if after is not None and before is not None:
            raise ValueError("after e before são mutuamente exclusivos")
        if not 1 <= limit <= 100:
            raise ValueError("limit deve estar entre 1 e 100")

        with self._lock:
            items = sorted(
                (
                    item
                    for item in self._events_by_id.values()
                    if item.device_id == device_id
                ),
                key=lambda item: item.ingestion_id,
            )

        if after is not None:
            selected = [item for item in items if item.ingestion_id > after][:limit]
            has_more_before = False
        else:
            eligible = (
                [item for item in items if item.ingestion_id < before]
                if before is not None
                else items
            )
            has_more_before = len(eligible) > limit
            selected = eligible[-limit:]

        if not selected:
            return EventPage((), None, None, has_more_before)

        return EventPage(
            events=tuple(selected),
            oldest_cursor=selected[0].ingestion_id,
            newest_cursor=selected[-1].ingestion_id,
            has_more_before=has_more_before,
        )

    def get_maneuver_event_detail(
        self,
        device_id: str,
        event_id: UUID,
    ) -> ManeuverEventDetail | None:
        with self._lock:
            selected = self._events_by_id.get(str(event_id))
            if selected is None or selected.device_id != device_id:
                return None
            maneuver_id = selected.event.maneuver_id
            events = tuple(sorted(
                (
                    item
                    for item in self._events_by_id.values()
                    if item.device_id == device_id
                    and item.event.maneuver_id == maneuver_id
                ),
                key=lambda item: item.ingestion_id,
            ))
        return ManeuverEventDetail(
            selected_event_id=event_id,
            maneuver_id=maneuver_id,
            events=events,
        )

    def upsert_push_installation(
        self,
        device_id,
        installation_id,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
    ):
        with self._lock:
            if device_id not in self._devices:
                return None
            now = self._clock()
            current = self._push_installations.get(installation_id)
            if current is not None and current.device_id != device_id:
                return None
            if current is None:
                installation = PushInstallation(
                    installation_id=installation_id,
                    device_id=device_id,
                    endpoint=endpoint,
                    p256dh=p256dh,
                    auth=auth,
                    preferences=PushPreferences(),
                    push_enabled_at=now,
                    last_seen_at=now,
                    last_foreground_at=None,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            else:
                installation = replace(
                    current,
                    endpoint=endpoint,
                    p256dh=p256dh,
                    auth=auth,
                    push_enabled_at=(
                        current.push_enabled_at if current.active else now
                    ),
                    last_seen_at=now,
                    active=True,
                    updated_at=now,
                )
            self._push_installations[installation_id] = installation
            return installation

    def get_push_installation(
        self,
        device_id,
        installation_id,
    ):
        with self._lock:
            installation = self._push_installations.get(installation_id)
            if installation is None or installation.device_id != device_id:
                return None
            return installation

    def update_push_preferences(
        self,
        device_id,
        installation_id,
        preferences: PushPreferences,
    ):
        with self._lock:
            current = self._push_installations.get(installation_id)
            if current is None or current.device_id != device_id:
                return None
            now = self._clock()
            updated = replace(
                current,
                preferences=preferences,
                last_seen_at=now,
                updated_at=now,
            )
            self._push_installations[installation_id] = updated
            return updated

    def touch_push_foreground(
        self,
        device_id,
        installation_id,
    ):
        with self._lock:
            current = self._push_installations.get(installation_id)
            if (
                current is None
                or current.device_id != device_id
                or not current.active
            ):
                return None
            now = self._clock()
            updated = replace(
                current,
                last_seen_at=now,
                last_foreground_at=now,
                updated_at=now,
            )
            self._push_installations[installation_id] = updated
            return updated

    def deactivate_push_installation(
        self,
        device_id,
        installation_id,
    ) -> bool:
        with self._lock:
            current = self._push_installations.get(installation_id)
            if current is None or current.device_id != device_id:
                return False
            now = self._clock()
            self._push_installations[installation_id] = replace(
                current,
                endpoint=None,
                p256dh=None,
                auth=None,
                active=False,
                last_seen_at=now,
                updated_at=now,
            )
            return True

    def list_active_push_installations(
        self,
        device_id: str,
    ) -> tuple[PushInstallation, ...]:
        with self._lock:
            return tuple(
                installation
                for installation in self._push_installations.values()
                if installation.device_id == device_id
                and installation.active
            )

    def claim_tracking_push_delivery(
        self,
        event_id,
        installation_id,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        with self._lock:
            event_key = str(event_id)
            installation = self._push_installations.get(installation_id)
            if (
                event_key not in self._tracking_events_by_id
                or installation is None
                or not installation.active
            ):
                return False
            key = (event_key, installation_id)
            now = self._clock()
            current = self._tracking_push_deliveries.get(key)
            if current is None:
                self._tracking_push_deliveries[key] = TrackingPushDelivery(
                    event_id=current_event_id(event_key),
                    installation_id=installation_id,
                    status=TrackingPushDeliveryStatus.SENDING,
                    claimed_at=now,
                    updated_at=now,
                )
                return True

            recoverable = (
                current.status is TrackingPushDeliveryStatus.RETRY_PENDING
                or (
                    current.status is TrackingPushDeliveryStatus.SENDING
                    and (now - current.claimed_at).total_seconds()
                    >= lease_seconds
                )
            )
            if not recoverable:
                return False
            self._tracking_push_deliveries[key] = replace(
                current,
                status=TrackingPushDeliveryStatus.SENDING,
                claimed_at=now,
                updated_at=now,
            )
            return True

    def set_tracking_push_delivery_status(
        self,
        event_id,
        installation_id,
        status: TrackingPushDeliveryStatus,
    ) -> None:
        with self._lock:
            event_key = str(event_id)
            key = (event_key, installation_id)
            now = self._clock()
            current = self._tracking_push_deliveries.get(key)
            if current is None:
                if (
                    event_key not in self._tracking_events_by_id
                    or installation_id not in self._push_installations
                ):
                    return
                self._tracking_push_deliveries[key] = TrackingPushDelivery(
                    event_id=current_event_id(event_key),
                    installation_id=installation_id,
                    status=status,
                    claimed_at=now,
                    updated_at=now,
                )
                return
            self._tracking_push_deliveries[key] = replace(
                current,
                status=status,
                updated_at=now,
            )

    def get_tracking_push_delivery(
        self,
        event_id,
        installation_id,
    ) -> TrackingPushDelivery | None:
        with self._lock:
            return self._tracking_push_deliveries.get(
                (str(event_id), installation_id)
            )

    def claim_push_delivery(
        self,
        event_id,
        installation_id,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        with self._lock:
            event_key = str(event_id)
            installation = self._push_installations.get(installation_id)
            if (
                event_key not in self._events_by_id
                or installation is None
                or not installation.active
            ):
                return False
            key = (event_key, installation_id)
            now = self._clock()
            current = self._push_deliveries.get(key)
            if current is None:
                self._push_deliveries[key] = PushDelivery(
                    event_id=current_event_id(event_key),
                    installation_id=installation_id,
                    status=PushDeliveryStatus.SENDING,
                    claimed_at=now,
                    updated_at=now,
                )
                return True

            recoverable = (
                current.status is PushDeliveryStatus.RETRY_PENDING
                or (
                    current.status is PushDeliveryStatus.SENDING
                    and (now - current.claimed_at).total_seconds()
                    >= lease_seconds
                )
            )
            if not recoverable:
                return False
            self._push_deliveries[key] = replace(
                current,
                status=PushDeliveryStatus.SENDING,
                claimed_at=now,
                updated_at=now,
            )
            return True

    def set_push_delivery_status(
        self,
        event_id,
        installation_id,
        status: PushDeliveryStatus,
    ) -> None:
        with self._lock:
            event_key = str(event_id)
            key = (event_key, installation_id)
            now = self._clock()
            current = self._push_deliveries.get(key)
            if current is None:
                if (
                    event_key not in self._events_by_id
                    or installation_id not in self._push_installations
                ):
                    return
                self._push_deliveries[key] = PushDelivery(
                    event_id=current_event_id(event_key),
                    installation_id=installation_id,
                    status=status,
                    claimed_at=now,
                    updated_at=now,
                )
                return
            self._push_deliveries[key] = replace(
                current,
                status=status,
                updated_at=now,
            )

    def get_push_delivery(
        self,
        event_id,
        installation_id,
    ):
        with self._lock:
            return self._push_deliveries.get(
                (str(event_id), installation_id)
            )


def current_event_id(value: str):
    from uuid import UUID, uuid4

    return UUID(value)
