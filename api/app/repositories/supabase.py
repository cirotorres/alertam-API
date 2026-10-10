from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.models.maneuver_event import ManeuverEventIn
from app.models.source_authority import (
    AuthorityGrantView,
    AuthorityMode,
    AuthorityReasonCode,
    AuthorityStatus,
    ManagedSnapshotAcceptanceResult,
    PublishUnderCurrentGrant,
    SideEffectPolicy,
    Source,
    SourceAuthorityRecord,
    SourceHeartbeatRecord,
    TransitionCandidate,
)
from app.models.source_heartbeat import SourceHeartbeatRequest, SourceHeartbeatResponse
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
    DeviceAuthRecord,
    MobileInstallationDisplayCodeConflictError,
    MobileInstallationRecord,
    MobileInstallationSwitchConflictError,
    MobilePairingCodeConflictError,
    MobilePairingCodeRedeemResult,
    MobilePairingCodeRedeemStatus,
    PersistenceUnavailableError,
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


class SupabaseDeviceRepository:
    def __init__(
        self,
        base_url: str,
        server_key: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._server_key = server_key
        self._client = client or httpx.Client(timeout=10.0)

    def _headers(self) -> dict[str, str]:
        headers = {
            "apikey": self._server_key,
            "Content-Type": "application/json",
        }
        if not self._server_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._server_key}"
        return headers

    def get_source_authority(
        self,
        device_id: str,
    ) -> SourceAuthorityRecord | None:
        return self._mapped_cloud_rpc(
            "get_device_source_authority",
            {"p_device_id": device_id},
            self._source_authority_from_mapping,
        )

    def get_current_grant(
        self,
        device_id: str,
    ) -> AuthorityGrantView | None:
        authority = self.get_source_authority(device_id)
        if authority is None or authority.mode is not AuthorityMode.MANAGED:
            return None
        if (
            authority.active_source is None
            or authority.authority_lease_id is None
            or authority.holder_instance_id is None
            or authority.lease_expires_at is None
        ):
            raise PersistenceUnavailableError()
        return AuthorityGrantView(
            device_id=authority.device_id,
            source=authority.active_source,
            authority_epoch=authority.authority_epoch,
            authority_lease_id=authority.authority_lease_id,
            holder_instance_id=authority.holder_instance_id,
            lease_expires_at=authority.lease_expires_at,
        )

    def get_source_heartbeat(
        self,
        device_id: str,
        source: Source,
        instance_id: UUID,
    ) -> SourceHeartbeatRecord | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/device_source_heartbeats",
                headers=self._headers(),
                params={
                    "select": (
                        "device_id,source,instance_id,last_heartbeat_at,"
                        "collection_healthy,process_healthy,healthy_since,"
                        "consecutive_healthy,last_collection_ok_at,"
                        "last_reported_generated_at,last_candidate_generated_at,"
                        "last_reason_code,persistent_state_ready,updated_at"
                    ),
                    "device_id": f"eq.{device_id}",
                    "source": f"eq.{source.value}",
                    "instance_id": f"eq.{instance_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta SourceHeartbeat inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta SourceHeartbeat inválida.")
            return self._source_heartbeat_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def record_source_heartbeat(
        self,
        device_id: str,
        source: Source,
        request: SourceHeartbeatRequest,
        *,
        cloud_binding_id: UUID | None = None,
    ) -> SourceHeartbeatResponse:
        payload = {
            "p_device_id": device_id,
            "p_source": source.value,
            "p_instance_id": str(request.instance_id),
            "p_process_healthy": request.process_healthy,
            "p_collection_healthy": request.collection_healthy,
            "p_last_reported_generated_at": (
                None if request.last_reported_generated_at is None
                else request.last_reported_generated_at.isoformat()
            ),
            "p_last_candidate_generated_at": (
                None if request.last_candidate_generated_at is None
                else request.last_candidate_generated_at.isoformat()
            ),
            "p_persistent_state_ready": request.persistent_state_ready,
            "p_cloud_binding_id": None if cloud_binding_id is None else str(cloud_binding_id),
        }
        def mapper(row: Any) -> SourceHeartbeatResponse:
            if not isinstance(row, dict):
                raise TypeError("invalid heartbeat RPC row")
            values = tuple(row[key] for key in (
                "status","reason_code","authority_epoch","authority_lease_id",
                "holder_instance_id","lease_expires_at","renewed",
            ))
            grant = None
            if all(values[i] is not None for i in (2,3,4,5)):
                expires_at = self._parse_datetime(values[5])
                if expires_at is None:
                    raise ValueError("missing grant expiry")
                grant = AuthorityGrantView(
                    device_id=device_id,source=source,authority_epoch=int(values[2]),
                    authority_lease_id=UUID(str(values[3])),
                    holder_instance_id=UUID(str(values[4])),
                    lease_expires_at=expires_at,
                )
            if not isinstance(values[6],bool):
                raise TypeError("invalid renewed")
            return SourceHeartbeatResponse(
                status=AuthorityStatus(str(values[0])),
                reason_code=(
                    None if values[1] is None else AuthorityReasonCode(str(values[1]))
                ),
                source=source,instance_id=request.instance_id,
                grant=grant,renewed=values[6],
            )
        response = self._mapped_cloud_rpc("record_source_heartbeat",payload,mapper)
        if response is None:
            raise PersistenceUnavailableError()
        return response

    def bootstrap_managed_source_authority(
        self,
        device_id: str,
    ) -> ManagedSnapshotAcceptanceResult:
        result = self._mapped_cloud_rpc(
            "bootstrap_managed_source_authority",
            {"p_device_id": device_id},
            self._managed_snapshot_result_from_mapping,
        )
        if result is None:
            raise PersistenceUnavailableError()
        return result

    def accept_current_grant_snapshot(
        self,
        command: PublishUnderCurrentGrant,
    ) -> ManagedSnapshotAcceptanceResult:
        candidate = command.candidate
        result = self._mapped_cloud_rpc(
            "accept_managed_snapshot_current_grant",
            {
                "p_device_id": candidate.device_id,
                "p_source": candidate.source.value,
                "p_authority_epoch": command.authority_epoch,
                "p_authority_lease_id": str(command.authority_lease_id),
                "p_holder_instance_id": str(command.holder_instance_id),
                "p_snapshot": candidate.snapshot,
                "p_snapshot_schema_version": candidate.snapshot_schema_version,
                "p_boot_id": str(candidate.boot_id),
                "p_sequence": candidate.sequence,
                "p_generated_at": candidate.generated_at.isoformat(),
            },
            self._managed_snapshot_result_from_mapping,
        )
        if result is None:
            raise PersistenceUnavailableError()
        return result

    def accept_transition_candidate(
        self,
        command: TransitionCandidate,
    ) -> ManagedSnapshotAcceptanceResult:
        candidate = command.candidate
        result = self._mapped_cloud_rpc(
            "accept_managed_snapshot_transition_candidate",
            {
                "p_device_id": candidate.device_id,
                "p_source": candidate.source.value,
                "p_holder_instance_id": str(candidate.holder_instance_id),
                "p_snapshot": candidate.snapshot,
                "p_snapshot_schema_version": candidate.snapshot_schema_version,
                "p_boot_id": str(candidate.boot_id),
                "p_sequence": candidate.sequence,
                "p_generated_at": candidate.generated_at.isoformat(),
            },
            self._managed_snapshot_result_from_mapping,
        )
        if result is None:
            raise PersistenceUnavailableError()
        return result

    def return_source_authority_to_legacy(
        self,
        device_id: str,
    ) -> SourceAuthorityRecord | None:
        return self._mapped_cloud_rpc(
            "return_source_authority_to_legacy",
            {"p_device_id": device_id},
            self._source_authority_from_mapping,
        )

    @classmethod
    def _source_authority_from_mapping(
        cls,
        row: Any,
    ) -> SourceAuthorityRecord:
        if not isinstance(row, dict):
            raise TypeError("SourceAuthority persistida inválida.")
        updated_at = cls._parse_datetime(row.get("updated_at"))
        if updated_at is None:
            raise ValueError("updated_at de SourceAuthority ausente.")
        return SourceAuthorityRecord(
            device_id=str(row["device_id"]),
            mode=AuthorityMode(str(row["mode"])),
            active_source=(
                None if row.get("active_source") is None
                else Source(str(row["active_source"]))
            ),
            authority_epoch=int(row["authority_epoch"]),
            authority_lease_id=(
                None if row.get("authority_lease_id") is None
                else UUID(str(row["authority_lease_id"]))
            ),
            holder_instance_id=(
                None if row.get("holder_instance_id") is None
                else UUID(str(row["holder_instance_id"]))
            ),
            lease_expires_at=cls._parse_datetime(row.get("lease_expires_at")),
            granted_at=cls._parse_datetime(row.get("granted_at")),
            last_renewed_at=cls._parse_datetime(row.get("last_renewed_at")),
            last_transition_at=cls._parse_datetime(row.get("last_transition_at")),
            transition_reason=(
                None if row.get("transition_reason") is None
                else AuthorityReasonCode(str(row["transition_reason"]))
            ),
            last_authoritative_snapshot_at=cls._parse_datetime(
                row.get("last_authoritative_snapshot_at")
            ),
            authoritative_snapshot_stale_since=cls._parse_datetime(
                row.get("authoritative_snapshot_stale_since")
            ),
            cloud_binding_id=(
                None if row.get("cloud_binding_id") is None
                else UUID(str(row["cloud_binding_id"]))
            ),
            realm_id=None if row.get("realm_id") is None else str(row["realm_id"]),
            observed_realm_epoch=(
                None if row.get("observed_realm_epoch") is None
                else int(row["observed_realm_epoch"])
            ),
            updated_at=updated_at,
        )

    @classmethod
    def _source_heartbeat_from_mapping(
        cls,
        row: Any,
    ) -> SourceHeartbeatRecord:
        if not isinstance(row, dict):
            raise TypeError("SourceHeartbeat persistido inválido.")
        last_heartbeat_at = cls._parse_datetime(row.get("last_heartbeat_at"))
        if last_heartbeat_at is None:
            raise ValueError("last_heartbeat_at ausente.")
        for flag in ("collection_healthy", "process_healthy"):
            if not isinstance(row.get(flag), bool):
                raise TypeError("Flag SourceHeartbeat inválida.")
        persistent = row.get("persistent_state_ready")
        if persistent is not None and not isinstance(persistent, bool):
            raise TypeError("persistent_state_ready inválido.")
        updated_at = cls._parse_datetime(row.get("updated_at"))
        return SourceHeartbeatRecord(
            device_id=str(row["device_id"]),
            source=Source(str(row["source"])),
            instance_id=UUID(str(row["instance_id"])),
            last_heartbeat_at=last_heartbeat_at,
            collection_healthy=row["collection_healthy"],
            process_healthy=row["process_healthy"],
            healthy_since=cls._parse_datetime(row.get("healthy_since")),
            consecutive_healthy=int(row["consecutive_healthy"]),
            last_collection_ok_at=cls._parse_datetime(row.get("last_collection_ok_at")),
            last_reported_generated_at=cls._parse_datetime(
                row.get("last_reported_generated_at")
            ),
            last_candidate_generated_at=cls._parse_datetime(
                row.get("last_candidate_generated_at")
            ),
            last_reason_code=(
                None if row.get("last_reason_code") is None
                else AuthorityReasonCode(str(row["last_reason_code"]))
            ),
            persistent_state_ready=persistent,
            updated_at=updated_at,
        )

    @classmethod
    def _managed_snapshot_result_from_mapping(
        cls,
        row: Any,
    ) -> ManagedSnapshotAcceptanceResult:
        if not isinstance(row, dict):
            raise TypeError("Resultado managed snapshot inválido.")
        source = Source(str(row["source"]))
        grant = None
        grant_fields = (
            row.get("authority_epoch"),
            row.get("authority_lease_id"),
            row.get("holder_instance_id"),
            row.get("lease_expires_at"),
        )
        if all(value is not None for value in grant_fields):
            expires_at = cls._parse_datetime(row.get("lease_expires_at"))
            if expires_at is None:
                raise ValueError("lease_expires_at ausente.")
            grant = AuthorityGrantView(
                device_id=str(row["device_id"]),
                source=source,
                authority_epoch=int(row["authority_epoch"]),
                authority_lease_id=UUID(str(row["authority_lease_id"])),
                holder_instance_id=UUID(str(row["holder_instance_id"])),
                lease_expires_at=expires_at,
            )
        return ManagedSnapshotAcceptanceResult(
            status=AuthorityStatus(str(row["status"])),
            reason_code=(
                None if row.get("reason_code") is None
                else AuthorityReasonCode(str(row["reason_code"]))
            ),
            received_at=cls._parse_datetime(row.get("received_at")),
            device_id=str(row["device_id"]),
            source=source,
            grant=grant,
            previous_source=(
                None if row.get("previous_source") is None
                else Source(str(row["previous_source"]))
            ),
            source_transition=bool(row["source_transition"]),
            side_effect_policy=SideEffectPolicy(str(row["side_effect_policy"])),
            previous_snapshot_for_side_effects=row.get("previous_snapshot"),
        )

    def get_device_auth(
        self,
        device_id: str,
    ) -> DeviceAuthRecord | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/devices",
                headers=self._headers(),
                params={
                    "select": (
                        "device_id,device_secret_hash,view_secret_hash,"
                        "description,enabled"
                    ),
                    "device_id": f"eq.{device_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de dispositivo inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de dispositivo inválida.")
            row = data[0]
            return DeviceAuthRecord(
                device_id=str(row["device_id"]),
                device_secret_hash=str(row["device_secret_hash"]),
                view_secret_hash=(
                    None
                    if row.get("view_secret_hash") is None
                    else str(row["view_secret_hash"])
                ),
                description=(
                    None
                    if row.get("description") is None
                    else str(row["description"])
                ),
                enabled=bool(row.get("enabled", True)),
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def ensure_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None:
        try:
            headers = {
                **self._headers(),
                "Prefer": "resolution=ignore-duplicates,return=representation",
            }
            response = self._client.post(
                f"{self._base_url}/rest/v1/webpilot_auth_realms",
                headers=headers,
                params={"on_conflict": "realm_id"},
                json={"realm_id": realm_id, "active": True},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return self._webpilot_auth_realm_from_mapping(data[0])
            return self.get_webpilot_auth_realm(realm_id)
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def get_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/webpilot_auth_realms",
                headers=self._headers(),
                params={
                    "select": "realm_id,active,created_at,updated_at",
                    "realm_id": f"eq.{realm_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de realm inválida.")
            if not data:
                return None
            if len(data) != 1:
                raise ValueError("Resposta de realm inválida.")
            return self._webpilot_auth_realm_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def set_webpilot_auth_realm_active(
        self,
        realm_id: str,
        active: bool,
    ) -> WebPilotAuthRealmRecord | None:
        return self._mapped_cloud_rpc(
            "set_webpilot_auth_realm_active",
            {"p_realm_id": realm_id, "p_active": active},
            self._webpilot_auth_realm_from_mapping,
        )

    def authorize_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        return self._mapped_cloud_rpc(
            "authorize_realm_device",
            {"p_realm_id": realm_id, "p_device_id": device_id},
            self._realm_device_authorization_from_mapping,
        )

    def revoke_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        return self._mapped_cloud_rpc(
            "revoke_realm_device",
            {"p_realm_id": realm_id, "p_device_id": device_id},
            self._realm_device_authorization_from_mapping,
        )

    def get_realm_device_authorization(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/webpilot_auth_realm_devices",
                headers=self._headers(),
                params={
                    "select": "realm_id,device_id,authorized_at,revoked_at",
                    "realm_id": f"eq.{realm_id}",
                    "device_id": f"eq.{device_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de membership inválida.")
            if not data:
                return None
            if len(data) != 1:
                raise ValueError("Resposta de membership inválida.")
            return self._realm_device_authorization_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def get_cloud_binding_authority(
        self,
        cloud_binding_id: UUID,
    ) -> CloudBindingAuthorityRecord | None:
        return self._mapped_cloud_rpc(
            "get_cloud_binding_authority",
            {"p_cloud_binding_id": str(cloud_binding_id)},
            self._cloud_binding_authority_from_mapping,
        )

    def get_active_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        bindings = self._get_cloud_bindings(device_id, active_only=True)
        return bindings[0] if bindings else None

    def list_cloud_bindings(
        self,
        device_id: str,
    ) -> tuple[CloudBindingRecord, ...]:
        return self._get_cloud_bindings(device_id, active_only=False)

    def ensure_cloud_binding(
        self,
        device_id: str,
        realm_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None:
        return self._mapped_cloud_rpc(
            "ensure_cloud_binding",
            {
                "p_device_id": device_id,
                "p_realm_id": realm_id,
                "p_credential_hash": credential_hash,
            },
            self._cloud_binding_from_mapping,
        )

    def rotate_cloud_binding(
        self,
        device_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None:
        return self._mapped_cloud_rpc(
            "rotate_cloud_binding",
            {
                "p_device_id": device_id,
                "p_credential_hash": credential_hash,
            },
            self._cloud_binding_from_mapping,
        )

    def revoke_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        return self._mapped_cloud_rpc(
            "revoke_cloud_binding",
            {"p_device_id": device_id},
            self._cloud_binding_from_mapping,
        )

    def set_required_provider_scope(
        self,
        realm_id: str,
        profile: ProviderScopeProfile,
    ) -> RequiredProviderScopeRecord | None:
        return self._mapped_cloud_rpc(
            "set_required_provider_scope",
            {
                "p_realm_id": realm_id,
                "p_scope_id": profile.scope_id,
                "p_schema_version": profile.schema_version,
                "p_capabilities": list(profile.capabilities),
            },
            self._required_provider_scope_from_mapping,
        )

    def get_required_provider_scope(
        self,
        realm_id: str,
    ) -> RequiredProviderScopeRecord | None:
        return self._get_session_broker_row(
            "webpilot_provider_scope_requirements",
            {
                "select": (
                    "realm_id,scope_id,schema_version,capabilities,updated_at"
                ),
                "realm_id": f"eq.{realm_id}",
                "limit": "1",
            },
            self._required_provider_scope_from_mapping,
        )

    def ensure_session_publisher(
        self,
        *,
        device_id: str,
        realm_id: str,
        publisher_id: UUID,
        provider_scope: ProviderScopeProfile,
    ) -> SessionPublisherRecord | None:
        return self._mapped_cloud_rpc(
            "ensure_session_publisher",
            {
                "p_device_id": device_id,
                "p_realm_id": realm_id,
                "p_publisher_id": str(publisher_id),
                "p_scope_id": provider_scope.scope_id,
                "p_scope_schema_version": provider_scope.schema_version,
                "p_scope_capabilities": list(provider_scope.capabilities),
            },
            self._session_publisher_from_mapping,
        )

    def get_session_publisher(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None:
        return self._get_session_broker_row(
            "webpilot_session_publishers",
            {
                "select": (
                    "publisher_id,realm_id,device_id,provider_scope_id,"
                    "provider_scope_schema_version,provider_scope_capabilities,"
                    "scope_status,scope_verified_at,last_generation,status,"
                    "created_at,updated_at,revoked_at"
                ),
                "publisher_id": f"eq.{publisher_id}",
                "limit": "1",
            },
            self._session_publisher_from_mapping,
        )

    def verify_session_publisher_scope(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None:
        return self._mapped_cloud_rpc(
            "verify_session_publisher_scope",
            {"p_publisher_id": str(publisher_id)},
            self._session_publisher_from_mapping,
        )

    def revoke_session_publisher(
        self,
        publisher_id: UUID,
    ) -> SessionPublisherRecord | None:
        return self._mapped_cloud_rpc(
            "revoke_session_publisher",
            {"p_publisher_id": str(publisher_id)},
            self._session_publisher_from_mapping,
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
        return self._mapped_cloud_rpc(
            "accept_session_lease",
            {
                "p_device_id": device_id,
                "p_realm_id": realm_id,
                "p_publisher_id": str(publisher_id),
                "p_lease_id": str(lease_id),
                "p_local_generation": local_generation,
                "p_payload_fingerprint": payload_fingerprint,
                "p_ciphertext": ciphertext,
                "p_nonce": nonce,
                "p_key_version": key_version,
                "p_payload_schema_version": payload_schema_version,
                "p_expires_at": (
                    None if expires_at is None else expires_at.isoformat()
                ),
            },
            self._session_lease_from_mapping,
        )

    def get_session_lease(
        self,
        lease_id: UUID,
    ) -> EncryptedSessionLeaseRecord | None:
        return self._get_session_broker_row(
            "webpilot_session_leases",
            {
                "select": (
                    "lease_id,realm_id,publisher_id,local_generation,realm_epoch,"
                    "payload_fingerprint,ciphertext,nonce,key_version,"
                    "payload_schema_version,received_at,expires_at,status,"
                    "revoked_at,invalidated_at"
                ),
                "lease_id": f"eq.{lease_id}",
                "limit": "1",
            },
            self._session_lease_from_mapping,
        )

    def get_current_session_lease(
        self,
        realm_id: str,
        *,
        now: datetime,
    ) -> EncryptedSessionLeaseRecord | None:
        return self._mapped_cloud_rpc(
            "get_current_session_lease",
            {
                "p_realm_id": realm_id,
                "p_now": now.isoformat(),
            },
            self._session_lease_from_mapping,
        )

    def revoke_session_lease(
        self,
        *,
        device_id: str,
        realm_id: str,
        lease_id: UUID,
    ) -> EncryptedSessionLeaseRecord | None:
        return self._mapped_cloud_rpc(
            "revoke_session_lease",
            {
                "p_device_id": device_id,
                "p_realm_id": realm_id,
                "p_lease_id": str(lease_id),
            },
            self._session_lease_from_mapping,
        )

    def invalidate_session_lease(
        self,
        *,
        realm_id: str,
        lease_id: UUID,
        realm_epoch: int,
    ) -> EncryptedSessionLeaseRecord | None:
        return self._mapped_cloud_rpc(
            "invalidate_session_lease",
            {
                "p_realm_id": realm_id,
                "p_lease_id": str(lease_id),
                "p_realm_epoch": realm_epoch,
            },
            self._session_lease_from_mapping,
        )

    def _get_session_broker_row(
        self,
        table: str,
        params: dict[str, str],
        mapper,
    ):
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/{table}",
                headers=self._headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta SessionBroker inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta SessionBroker inválida.")
            return mapper(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def _mapped_cloud_rpc(
        self,
        name: str,
        payload: dict[str, Any],
        mapper,
    ):
        row = self._cloud_rpc_row(name, payload)
        if row is None:
            return None
        try:
            return mapper(row)
        except (KeyError, TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def _cloud_rpc_row(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/{name}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta RPC Cloud inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta RPC Cloud inválida.")
            return data[0]
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text
            if "cloud_binding_conflict" in response_text:
                raise CloudBindingConflictError() from exc
            if "session_publisher_conflict" in response_text:
                raise SessionPublisherConflictError() from exc
            if "session_lease_generation_conflict" in response_text:
                raise SessionLeaseGenerationConflictError() from exc
            if "session_lease_replay" in response_text:
                raise SessionLeaseReplayError() from exc
            raise PersistenceUnavailableError() from exc
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def _get_cloud_bindings(
        self,
        device_id: str,
        *,
        active_only: bool,
    ) -> tuple[CloudBindingRecord, ...]:
        try:
            params = {
                "select": (
                    "cloud_binding_id,device_id,realm_id,credential_hash,"
                    "credential_version,status,created_at,updated_at,revoked_at"
                ),
                "device_id": f"eq.{device_id}",
                "order": "lifecycle_order.asc",
            }
            if active_only:
                params["status"] = "eq.active"
                params["limit"] = "1"
            response = self._client.get(
                f"{self._base_url}/rest/v1/cloud_bindings",
                headers=self._headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de binding inválida.")
            return tuple(self._cloud_binding_from_mapping(row) for row in data)
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    @classmethod
    def _required_provider_scope_from_mapping(
        cls,
        row: Any,
    ) -> RequiredProviderScopeRecord:
        if not isinstance(row, dict):
            raise TypeError("Provider scope persistido inválido.")
        updated_at = cls._parse_datetime(row.get("updated_at"))
        if updated_at is None:
            raise ValueError("updated_at ausente.")
        capabilities = row.get("capabilities")
        if not isinstance(capabilities, list):
            raise TypeError("capabilities inválidas.")
        return RequiredProviderScopeRecord(
            realm_id=str(row["realm_id"]),
            profile=ProviderScopeProfile(
                scope_id=str(row["scope_id"]),
                schema_version=int(row["schema_version"]),
                capabilities=tuple(str(item) for item in capabilities),
            ),
            updated_at=updated_at,
        )

    @classmethod
    def _session_publisher_from_mapping(
        cls,
        row: Any,
    ) -> SessionPublisherRecord:
        if not isinstance(row, dict):
            raise TypeError("Publisher persistido inválido.")
        capabilities = row.get("provider_scope_capabilities")
        if not isinstance(capabilities, list):
            raise TypeError("capabilities de publisher inválidas.")
        created_at = cls._parse_datetime(row.get("created_at"))
        updated_at = cls._parse_datetime(row.get("updated_at"))
        if created_at is None or updated_at is None:
            raise ValueError("timestamps de publisher ausentes.")
        return SessionPublisherRecord(
            publisher_id=UUID(str(row["publisher_id"])),
            realm_id=str(row["realm_id"]),
            device_id=str(row["device_id"]),
            provider_scope=ProviderScopeProfile(
                scope_id=str(row["provider_scope_id"]),
                schema_version=int(row["provider_scope_schema_version"]),
                capabilities=tuple(str(item) for item in capabilities),
            ),
            scope_status=ScopeStatus(str(row["scope_status"])),
            scope_verified_at=cls._parse_datetime(row.get("scope_verified_at")),
            last_generation=int(row["last_generation"]),
            status=SessionPublisherStatus(str(row["status"])),
            created_at=created_at,
            updated_at=updated_at,
            revoked_at=cls._parse_datetime(row.get("revoked_at")),
        )

    @classmethod
    def _session_lease_from_mapping(
        cls,
        row: Any,
    ) -> EncryptedSessionLeaseRecord:
        if not isinstance(row, dict):
            raise TypeError("SessionLease persistida inválida.")
        received_at = cls._parse_datetime(row.get("received_at"))
        if received_at is None:
            raise ValueError("received_at ausente.")
        return EncryptedSessionLeaseRecord(
            lease_id=UUID(str(row["lease_id"])),
            realm_id=str(row["realm_id"]),
            publisher_id=UUID(str(row["publisher_id"])),
            local_generation=int(row["local_generation"]),
            realm_epoch=int(row["realm_epoch"]),
            payload_fingerprint=str(row["payload_fingerprint"]),
            ciphertext=str(row["ciphertext"]),
            nonce=str(row["nonce"]),
            key_version=int(row["key_version"]),
            payload_schema_version=int(row["payload_schema_version"]),
            received_at=received_at,
            expires_at=cls._parse_datetime(row.get("expires_at")),
            status=SessionLeaseStatus(str(row["status"])),
            revoked_at=cls._parse_datetime(row.get("revoked_at")),
            invalidated_at=cls._parse_datetime(row.get("invalidated_at")),
        )

    @classmethod
    def _webpilot_auth_realm_from_mapping(
        cls,
        row: Any,
    ) -> WebPilotAuthRealmRecord:
        if not isinstance(row, dict):
            raise TypeError("Realm persistido inválido.")
        created_at = cls._parse_datetime(row.get("created_at"))
        updated_at = cls._parse_datetime(row.get("updated_at"))
        if created_at is None or updated_at is None:
            raise ValueError("Timestamps de realm ausentes.")
        return WebPilotAuthRealmRecord(
            realm_id=str(row["realm_id"]),
            active=bool(row["active"]),
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def _realm_device_authorization_from_mapping(
        cls,
        row: Any,
    ) -> RealmDeviceAuthorizationRecord:
        if not isinstance(row, dict):
            raise TypeError("Membership persistida inválida.")
        authorized_at = cls._parse_datetime(row.get("authorized_at"))
        if authorized_at is None:
            raise ValueError("authorized_at ausente.")
        return RealmDeviceAuthorizationRecord(
            realm_id=str(row["realm_id"]),
            device_id=str(row["device_id"]),
            authorized_at=authorized_at,
            revoked_at=cls._parse_datetime(row.get("revoked_at")),
        )

    @classmethod
    def _cloud_binding_authority_from_mapping(
        cls,
        row: Any,
    ) -> CloudBindingAuthorityRecord:
        if not isinstance(row, dict):
            raise TypeError("Autoridade persistida inválida.")
        for flag in (
            "device_enabled",
            "realm_active",
            "membership_active",
        ):
            if not isinstance(row.get(flag), bool):
                raise TypeError("Flag de autoridade persistida inválida.")
        return CloudBindingAuthorityRecord(
            cloud_binding_id=UUID(str(row["cloud_binding_id"])),
            device_id=str(row["device_id"]),
            realm_id=str(row["realm_id"]),
            credential_hash=str(row["credential_hash"]),
            status=CloudBindingStatus(str(row["status"])),
            device_enabled=row["device_enabled"],
            realm_active=row["realm_active"],
            membership_active=row["membership_active"],
        )

    @classmethod
    def _cloud_binding_from_mapping(
        cls,
        row: Any,
    ) -> CloudBindingRecord:
        if not isinstance(row, dict):
            raise TypeError("Binding persistido inválido.")
        created_at = cls._parse_datetime(row.get("created_at"))
        updated_at = cls._parse_datetime(row.get("updated_at"))
        if created_at is None or updated_at is None:
            raise ValueError("Timestamps de binding ausentes.")
        return CloudBindingRecord(
            cloud_binding_id=UUID(str(row["cloud_binding_id"])),
            device_id=str(row["device_id"]),
            realm_id=str(row["realm_id"]),
            credential_hash=str(row["credential_hash"]),
            credential_version=int(row["credential_version"]),
            status=CloudBindingStatus(str(row["status"])),
            created_at=created_at,
            updated_at=updated_at,
            revoked_at=cls._parse_datetime(row.get("revoked_at")),
        )

    def ensure_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str = "other",
        display_code: str | None = None,
    ) -> MobileInstallationRecord | None:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/ensure_mobile_installation",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                    "p_platform": platform,
                    "p_display_code": display_code,
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de instalação inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de instalação inválida.")
            return self._mobile_installation_from_mapping(data[0])
        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code == 409
                and "mobile_installations_display_code_unique"
                in exc.response.text
            ):
                raise MobileInstallationDisplayCodeConflictError() from exc
            raise PersistenceUnavailableError() from exc
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def get_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> MobileInstallationRecord | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/mobile_installations",
                headers=self._headers(),
                params={
                    "select": (
                        "installation_id,device_id,active,"
                        "created_at,last_seen_at,revoked_at,"
                        "platform,display_code"
                    ),
                    "device_id": f"eq.{device_id}",
                    "installation_id": f"eq.{installation_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de instalação inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de instalação inválida.")
            return self._mobile_installation_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def list_mobile_installations(
        self,
        device_id: str,
        *,
        revoked_since: datetime,
    ) -> tuple[MobileInstallationRecord, ...]:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/list_mobile_installations",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_revoked_since": revoked_since.isoformat(),
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de instalações inválida.")
            if not all(isinstance(item, dict) for item in data):
                raise ValueError("Resposta de instalações inválida.")
            return tuple(
                self._mobile_installation_from_mapping(item)
                for item in data
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def touch_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str,
    ) -> MobileInstallationRecord | None:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/touch_mobile_installation",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                    "p_platform": platform,
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de instalação inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de instalação inválida.")
            return self._mobile_installation_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def revoke_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/revoke_mobile_installation",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            updated = row["updated"]
            if not isinstance(updated, bool):
                raise TypeError("Resultado de revogação inválido.")
            return updated
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

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
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/switch_mobile_installation",
                headers=self._headers(),
                json={
                    "p_switch_id": str(switch_id),
                    "p_from_device_id": from_device_id,
                    "p_from_installation_id": str(from_installation_id),
                    "p_to_device_id": to_device_id,
                    "p_to_installation_id": str(to_installation_id),
                    "p_platform": platform,
                    "p_display_code": display_code,
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de troca mobile inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de troca mobile inválida.")
            return self._mobile_installation_from_mapping(data[0])
        except httpx.HTTPStatusError as exc:
            text = exc.response.text
            if "mobile_installations_display_code_unique" in text:
                raise MobileInstallationDisplayCodeConflictError() from exc
            if "mobile_session_switch_conflict" in text:
                raise MobileInstallationSwitchConflictError() from exc
            raise PersistenceUnavailableError() from exc
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    @classmethod
    def _mobile_installation_from_mapping(
        cls,
        row: dict[str, Any],
    ) -> MobileInstallationRecord:
        created_at = cls._parse_datetime(row.get("created_at"))
        last_seen_at = cls._parse_datetime(row.get("last_seen_at"))
        revoked_at = cls._parse_datetime(row.get("revoked_at"))
        if created_at is None or last_seen_at is None:
            raise ValueError("Timestamp de instalação ausente.")
        active = row.get("active")
        if not isinstance(active, bool):
            raise TypeError("active inválido.")
        platform = row.get("platform")
        display_code = row.get("display_code")
        if not isinstance(platform, str) or not isinstance(display_code, str):
            raise TypeError("Metadados de instalação inválidos.")
        return MobileInstallationRecord(
            installation_id=UUID(str(row["installation_id"])),
            device_id=str(row["device_id"]),
            active=active,
            created_at=created_at,
            last_seen_at=last_seen_at,
            revoked_at=revoked_at,
            platform=platform,
            display_code=display_code,
        )

    def get_snapshot(
        self,
        device_id: str,
    ) -> StoredSnapshot | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/devices",
                headers=self._headers(),
                params={
                    "select": (
                        "device_id,snapshot,snapshot_schema_version,"
                        "boot_id,sequence,generated_at,received_at"
                    ),
                    "device_id": f"eq.{device_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de snapshot inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de snapshot inválida.")

            row = data[0]
            if row.get("snapshot") is None:
                return None
            if not isinstance(row["snapshot"], dict):
                raise TypeError("Snapshot persistido inválido.")

            generated_at = self._parse_datetime(row.get("generated_at"))
            received_at = self._parse_datetime(row.get("received_at"))
            if generated_at is None or received_at is None:
                raise ValueError("Metadados de snapshot ausentes.")

            return StoredSnapshot(
                device_id=str(row["device_id"]),
                snapshot=row["snapshot"],
                snapshot_schema_version=int(
                    row["snapshot_schema_version"]
                ),
                boot_id=UUID(str(row["boot_id"])),
                sequence=int(row["sequence"]),
                generated_at=generated_at,
                received_at=received_at,
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def replace_mobile_pairing_code(
        self,
        device_id: str,
        code_hash: str,
        *,
        expires_at: datetime,
    ) -> bool:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/replace_mobile_pairing_code",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_code_hash": code_hash,
                    "p_expires_at": expires_at.isoformat(),
                },
            )
            if response.status_code == 409:
                raise MobilePairingCodeConflictError()
            response.raise_for_status()
            row = self._extract_row(response.json())
            updated = row["updated"]
            if not isinstance(updated, bool):
                raise TypeError("Resultado de código mobile inválido.")
            return updated
        except MobilePairingCodeConflictError:
            raise
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def redeem_mobile_pairing_code(
        self,
        code_hash: str,
        ticket_hash: str,
        *,
        ticket_expires_at: datetime,
        now: datetime,
    ) -> MobilePairingCodeRedeemResult:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/redeem_mobile_pairing_code",
                headers=self._headers(),
                json={
                    "p_code_hash": code_hash,
                    "p_ticket_hash": ticket_hash,
                    "p_ticket_expires_at": ticket_expires_at.isoformat(),
                    "p_now": now.isoformat(),
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            status = MobilePairingCodeRedeemStatus(str(row["status"]))
            expires_at = self._parse_datetime(row.get("ticket_expires_at"))
            return MobilePairingCodeRedeemResult(
                status=status,
                device_id=(
                    None
                    if row.get("device_id") is None
                    else str(row["device_id"])
                ),
                ticket_expires_at=expires_at,
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def validate_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        *,
        now: datetime,
    ) -> bool:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/validate_mobile_pairing_ticket",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_ticket_hash": ticket_hash,
                    "p_now": now.isoformat(),
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            valid = row["valid"]
            if not isinstance(valid, bool):
                raise TypeError("Resultado de ticket mobile inválido.")
            return valid
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def consume_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        purpose: str,
        *,
        now: datetime,
    ) -> bool:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/consume_mobile_pairing_ticket",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_ticket_hash": ticket_hash,
                    "p_purpose": purpose,
                    "p_now": now.isoformat(),
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            valid = row["valid"]
            if not isinstance(valid, bool):
                raise TypeError("Resultado de consumo mobile inválido.")
            return valid
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/rotate_device_view_secret",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_view_secret_hash": view_secret_hash,
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            updated = row["updated"]
            if not isinstance(updated, bool):
                raise TypeError("Resultado de rotação inválido.")
            return updated
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def accept_snapshot_atomic(
        self,
        candidate: SnapshotCandidate,
    ) -> AcceptSnapshotResult:
        payload = {
            "p_device_id": candidate.device_id,
            "p_snapshot": candidate.snapshot,
            "p_snapshot_schema_version": candidate.snapshot_schema_version,
            "p_boot_id": str(candidate.boot_id),
            "p_sequence": candidate.sequence,
            "p_generated_at": candidate.generated_at.isoformat(),
        }
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/accept_device_snapshot",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            status = AcceptSnapshotStatus(row["status"])
            received_at = self._parse_datetime(row.get("received_at"))
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

        return AcceptSnapshotResult(
            status=status,
            received_at=received_at,
        )

    @staticmethod
    def _extract_row(data: Any) -> dict[str, Any]:
        if isinstance(data, list):
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta RPC inválida.")
            return data[0]
        if isinstance(data, dict):
            return data
        raise ValueError("Resposta RPC inválida.")

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("received_at inválido.")
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            raise ValueError("received_at sem timezone.")
        return parsed

    def accept_maneuver_event_atomic(
        self,
        device_id: str,
        event: ManeuverEventIn,
    ) -> AcceptEventResult:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/accept_maneuver_event",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_event": event.canonical_payload(),
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            status = AcceptEventStatus(str(row["status"]))
            stored = None
            if row.get("ingestion_id") is not None:
                ingested_at = self._parse_datetime(row.get("ingested_at"))
                if ingested_at is None:
                    raise ValueError("ingested_at ausente")
                stored = StoredManeuverEvent(
                    ingestion_id=int(row["ingestion_id"]),
                    device_id=device_id,
                    event=ManeuverEventIn.model_validate(row["event_payload"]),
                    ingested_at=ingested_at,
                )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc
        return AcceptEventResult(status=status, stored=stored)

    @staticmethod
    def _normalize_vessel_name(value: str) -> str:
        return " ".join(value.upper().split())

    @classmethod
    def _vessel_matches(
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
        return cls._normalize_vessel_name(candidate_name) == (
            cls._normalize_vessel_name(requested_name)
        )

    def find_vessel_evidence(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
    ) -> VesselEvidence | None:
        snapshot = self.get_snapshot(device_id)
        if snapshot is not None:
            vessels = snapshot.snapshot.get("vessels", [])
            if isinstance(vessels, list):
                for raw in vessels:
                    if not isinstance(raw, dict):
                        continue
                    name = str(raw.get("name", ""))
                    raw_imo = raw.get("imo")
                    imo = None if raw_imo is None else str(raw_imo)
                    if not self._vessel_matches(
                        vessel_imo, vessel_name, imo, name
                    ):
                        continue
                    identity = (
                        f"IMO:{imo}"
                        if imo
                        else f"NAME:{self._normalize_vessel_name(name)}"
                    )
                    return VesselEvidence(
                        vessel_identity=identity,
                        vessel_imo=imo,
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

        try:
            tracking_response = self._client.get(
                f"{self._base_url}/rest/v1/vessel_tracking_events",
                headers=self._headers(),
                params={
                    "select": "event_payload",
                    "device_id": f"eq.{device_id}",
                    "order": "ingestion_id.desc",
                },
            )
            tracking_response.raise_for_status()
            maneuver_response = self._client.get(
                f"{self._base_url}/rest/v1/maneuver_events",
                headers=self._headers(),
                params={
                    "select": "event_payload",
                    "device_id": f"eq.{device_id}",
                    "order": "ingestion_id.desc",
                },
            )
            maneuver_response.raise_for_status()
            tracking_rows = tracking_response.json()
            maneuver_rows = maneuver_response.json()
            if not isinstance(tracking_rows, list) or not isinstance(
                maneuver_rows, list
            ):
                raise ValueError("Resposta de evidência inválida.")
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

        for row in tracking_rows:
            if not isinstance(row, dict):
                continue
            try:
                event = VesselTrackingEventIn.model_validate(
                    row["event_payload"]
                )
            except (KeyError, TypeError, ValueError):
                continue
            if not self._vessel_matches(
                vessel_imo, vessel_name, event.vessel_imo, event.vessel_name
            ):
                continue
            return VesselEvidence(
                vessel_identity=event.vessel_identity,
                vessel_imo=event.vessel_imo,
                vessel_name=event.vessel_name,
                current=event.current.model_dump(mode="json"),
                observed_at=event.occurred_at,
            )

        for row in maneuver_rows:
            if not isinstance(row, dict):
                continue
            try:
                event = ManeuverEventIn.model_validate(row["event_payload"])
            except (KeyError, TypeError, ValueError):
                continue
            if not self._vessel_matches(
                vessel_imo, vessel_name, event.vessel_imo, event.vessel_name
            ):
                continue
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

    @classmethod
    def _tracked_vessel_from_mapping(
        cls,
        row: dict[str, Any],
    ) -> TrackedVesselRecord:
        started_at = cls._parse_datetime(row.get("started_at"))
        stopped_at = cls._parse_datetime(row.get("stopped_at"))
        last_seen_at = cls._parse_datetime(row.get("last_seen_at"))
        if started_at is None:
            raise ValueError("started_at ausente.")
        active = row.get("active")
        if not isinstance(active, bool):
            raise TypeError("active inválido.")
        current = row.get("current")
        if current is not None and not isinstance(current, dict):
            raise TypeError("current inválido.")
        return TrackedVesselRecord(
            tracked_vessel_id=UUID(str(row["tracked_vessel_id"])),
            device_id=str(row["device_id"]),
            installation_id=UUID(str(row["installation_id"])),
            vessel_identity=str(row["vessel_identity"]),
            vessel_imo=(
                None
                if row.get("vessel_imo") is None
                else str(row["vessel_imo"])
            ),
            vessel_name=str(row["vessel_name"]),
            started_at=started_at,
            active=active,
            stopped_at=stopped_at,
            last_seen_at=last_seen_at,
            current=current,
        )

    def upsert_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        evidence: VesselEvidence,
    ) -> TrackedVesselRecord | None:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/upsert_tracked_vessel",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                    "p_vessel_identity": evidence.vessel_identity,
                    "p_vessel_imo": evidence.vessel_imo,
                    "p_vessel_name": evidence.vessel_name,
                    "p_current": evidence.current,
                    "p_last_seen_at": (
                        None
                        if evidence.observed_at is None
                        else evidence.observed_at.isoformat()
                    ),
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de tracking inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de tracking inválida.")
            return self._tracked_vessel_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def list_tracked_vessels(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> tuple[TrackedVesselRecord, ...]:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/tracked_vessels",
                headers=self._headers(),
                params={
                    "select": (
                        "tracked_vessel_id,device_id,installation_id,"
                        "vessel_identity,vessel_imo,vessel_name,"
                        "started_at,active,stopped_at,last_seen_at,current"
                    ),
                    "device_id": f"eq.{device_id}",
                    "installation_id": f"eq.{installation_id}",
                    "active": "eq.true",
                    "order": "started_at.asc",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de tracking inválida.")
            return tuple(
                self._tracked_vessel_from_mapping(row)
                for row in data
                if isinstance(row, dict)
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def get_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/tracked_vessels",
                headers=self._headers(),
                params={
                    "select": (
                        "tracked_vessel_id,device_id,installation_id,"
                        "vessel_identity,vessel_imo,vessel_name,"
                        "started_at,active,stopped_at,last_seen_at,current"
                    ),
                    "device_id": f"eq.{device_id}",
                    "installation_id": f"eq.{installation_id}",
                    "tracked_vessel_id": f"eq.{tracked_vessel_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de tracking inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de tracking inválida.")
            return self._tracked_vessel_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def deactivate_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/deactivate_tracked_vessel",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                    "p_tracked_vessel_id": str(tracked_vessel_id),
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Resposta de tracking inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de tracking inválida.")
            return self._tracked_vessel_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def project_tracked_vessels(
        self,
        device_id: str,
        *,
        vessel_identity: str,
        vessel_imo: str | None,
        vessel_name: str,
        observed_at: datetime,
        replace_current: bool,
        current: dict[str, Any] | None = None,
        patch: dict[str, Any] | None = None,
    ) -> int:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/project_tracked_vessels",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_vessel_identity": vessel_identity,
                    "p_vessel_imo": vessel_imo,
                    "p_vessel_name": vessel_name,
                    "p_observed_at": observed_at.isoformat(),
                    "p_replace_current": replace_current,
                    "p_current": current,
                    "p_patch": patch,
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, int):
                raise TypeError("Resultado de projeção inválido.")
            return data
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def list_tracked_vessel_event_records(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> tuple[VesselEventRecord, ...]:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/list_tracked_vessel_timeline",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                    "p_tracked_vessel_id": str(tracked_vessel_id),
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Timeline inválida.")
            result: list[VesselEventRecord] = []
            for row in data:
                if not isinstance(row, dict):
                    raise TypeError("Timeline inválida.")
                kind = str(row["kind"])
                if kind == "MANEUVER":
                    event = ManeuverEventIn.model_validate(row["event_payload"])
                elif kind == "TRACKING":
                    event = VesselTrackingEventIn.model_validate(
                        row["event_payload"]
                    )
                else:
                    raise ValueError("kind inválido")
                ingested_at = self._parse_datetime(row.get("ingested_at"))
                if ingested_at is None:
                    raise ValueError("ingested_at ausente")
                result.append(VesselEventRecord(
                    kind=kind,
                    ingestion_id=int(row["ingestion_id"]),
                    ingested_at=ingested_at,
                    event=event,
                ))
            return tuple(result)
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def latest_tracking_event_cursor(
        self,
        device_id: str,
    ) -> int | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/vessel_tracking_events",
                headers=self._headers(),
                params={
                    "select": "ingestion_id",
                    "device_id": f"eq.{device_id}",
                    "order": "ingestion_id.desc",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Cursor inválido.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Cursor inválido.")
            return int(data[0]["ingestion_id"])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def list_installation_tracking_events(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        after: int,
        limit: int,
    ) -> tuple[InstallationTrackingEventRecord, ...]:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/list_installation_tracking_events",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_installation_id": str(installation_id),
                    "p_after": after,
                    "p_limit": limit,
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Feed inválido.")
            result: list[InstallationTrackingEventRecord] = []
            for row in data:
                if not isinstance(row, dict):
                    raise TypeError("Feed inválido.")
                event = VesselTrackingEventIn.model_validate(
                    row["event_payload"]
                )
                ingested_at = self._parse_datetime(row.get("ingested_at"))
                if ingested_at is None:
                    raise ValueError("ingested_at ausente")
                stored = StoredVesselTrackingEvent(
                    ingestion_id=int(row["ingestion_id"]),
                    device_id=device_id,
                    event=event,
                    ingested_at=ingested_at,
                )
                result.append(InstallationTrackingEventRecord(
                    tracked_vessel_id=UUID(str(row["tracked_vessel_id"])),
                    stored=stored,
                ))
            return tuple(result)
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

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
        for tracked in self.list_tracked_vessels(
            device_id,
            installation_id,
        ):
            if tracked.started_at > occurred_at:
                continue
            if tracked.vessel_identity == vessel_identity:
                return tracked
            if vessel_imo is not None:
                if tracked.vessel_imo == vessel_imo:
                    return tracked
                if (
                    tracked.vessel_imo is None
                    and self._normalize_vessel_name(tracked.vessel_name)
                    == self._normalize_vessel_name(vessel_name)
                ):
                    return tracked
                continue
            if (
                tracked.vessel_imo is None
                and self._normalize_vessel_name(tracked.vessel_name)
                == self._normalize_vessel_name(vessel_name)
            ):
                return tracked
        return None

    def accept_vessel_tracking_event_atomic(
        self,
        device_id: str,
        event: VesselTrackingEventIn,
    ) -> AcceptTrackingEventResult:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/accept_vessel_tracking_event",
                headers=self._headers(),
                json={
                    "p_device_id": device_id,
                    "p_event": event.canonical_payload(),
                },
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            status = AcceptTrackingEventStatus(str(row["status"]))
            stored = None
            if row.get("ingestion_id") is not None:
                ingested_at = self._parse_datetime(row.get("ingested_at"))
                if ingested_at is None:
                    raise ValueError("ingested_at ausente")
                stored = StoredVesselTrackingEvent(
                    ingestion_id=int(row["ingestion_id"]),
                    device_id=device_id,
                    event=VesselTrackingEventIn.model_validate(
                        row["event_payload"]
                    ),
                    ingested_at=ingested_at,
                )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc
        return AcceptTrackingEventResult(status=status, stored=stored)

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

        descending = after is None
        params: dict[str, str] = {
            "select": "ingestion_id,device_id,event_payload,ingested_at",
            "device_id": f"eq.{device_id}",
            "order": "ingestion_id.desc" if descending else "ingestion_id.asc",
            "limit": str(limit + 1 if descending else limit),
        }
        if after is not None:
            params["ingestion_id"] = f"gt.{after}"
        elif before is not None:
            params["ingestion_id"] = f"lt.{before}"

        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/maneuver_events",
                headers=self._headers(),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de eventos inválida.")
            has_more_before = descending and len(data) > limit
            rows = data[:limit]
            if descending:
                rows = list(reversed(rows))
            events = tuple(
                self._stored_event_from_mapping(row)
                for row in rows
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

        return EventPage(
            events=events,
            oldest_cursor=events[0].ingestion_id if events else None,
            newest_cursor=events[-1].ingestion_id if events else None,
            has_more_before=has_more_before,
        )

    def get_maneuver_event_detail(
        self,
        device_id: str,
        event_id: UUID,
    ) -> ManeuverEventDetail | None:
        try:
            selected_response = self._client.get(
                f"{self._base_url}/rest/v1/maneuver_events",
                headers=self._headers(),
                params={
                    "select": "event_id,maneuver_id",
                    "device_id": f"eq.{device_id}",
                    "event_id": f"eq.{event_id}",
                    "limit": "1",
                },
            )
            selected_response.raise_for_status()
            selected_rows = selected_response.json()
            if not isinstance(selected_rows, list):
                raise TypeError("Resposta de detalhe inválida.")
            if not selected_rows:
                return None
            if len(selected_rows) != 1 or not isinstance(selected_rows[0], dict):
                raise ValueError("Resposta de detalhe inválida.")
            maneuver_id = UUID(str(selected_rows[0]["maneuver_id"]))

            cycle_response = self._client.get(
                f"{self._base_url}/rest/v1/maneuver_events",
                headers=self._headers(),
                params={
                    "select": (
                        "ingestion_id,device_id,event_payload,ingested_at"
                    ),
                    "device_id": f"eq.{device_id}",
                    "maneuver_id": f"eq.{maneuver_id}",
                    "order": "ingestion_id.asc",
                },
            )
            cycle_response.raise_for_status()
            cycle_rows = cycle_response.json()
            if not isinstance(cycle_rows, list):
                raise TypeError("Resposta de detalhe inválida.")
            events = tuple(
                self._stored_event_from_mapping(row)
                for row in cycle_rows
            )
            if not events or not any(
                item.event.event_id == event_id for item in events
            ):
                return None
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

        return ManeuverEventDetail(
            selected_event_id=event_id,
            maneuver_id=maneuver_id,
            events=events,
        )

    def _stored_event_from_mapping(self, row: Any) -> StoredManeuverEvent:
        if not isinstance(row, dict):
            raise TypeError("Evento persistido inválido.")
        ingested_at = self._parse_datetime(row.get("ingested_at"))
        if ingested_at is None:
            raise ValueError("ingested_at ausente")
        return StoredManeuverEvent(
            ingestion_id=int(row["ingestion_id"]),
            device_id=str(row["device_id"]),
            event=ManeuverEventIn.model_validate(row["event_payload"]),
            ingested_at=ingested_at,
        )

    def upsert_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushInstallation | None:
        return self._push_installation_rpc(
            "upsert_push_installation",
            {
                "p_device_id": device_id,
                "p_installation_id": str(installation_id),
                "p_endpoint": endpoint,
                "p_p256dh": p256dh,
                "p_auth": auth,
            },
        )

    def get_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/push_installations",
                headers=self._headers(),
                params={
                    "select": "*",
                    "device_id": f"eq.{device_id}",
                    "installation_id": f"eq.{installation_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de instalação inválida.")
            if not data:
                return None
            if len(data) != 1:
                raise ValueError("Resposta de instalação inválida.")
            return self._push_installation_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def update_push_preferences(
        self,
        device_id: str,
        installation_id: UUID,
        preferences: PushPreferences,
    ) -> PushInstallation | None:
        return self._push_installation_rpc(
            "update_push_preferences",
            {
                "p_device_id": device_id,
                "p_installation_id": str(installation_id),
                "p_confirmed": preferences.confirmed,
                "p_updated": preferences.updated,
                "p_completed": preferences.completed,
                "p_cancelled": preferences.cancelled,
                "p_anchored": preferences.anchored,
            },
        )

    def touch_push_foreground(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None:
        return self._push_installation_rpc(
            "touch_push_foreground",
            {
                "p_device_id": device_id,
                "p_installation_id": str(installation_id),
            },
        )

    def deactivate_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool:
        return self._push_boolean_rpc(
            "deactivate_push_installation",
            {
                "p_device_id": device_id,
                "p_installation_id": str(installation_id),
            },
            "updated",
        )

    def list_active_push_installations(
        self,
        device_id: str,
    ) -> tuple[PushInstallation, ...]:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/push_installations",
                headers=self._headers(),
                params={
                    "select": "*",
                    "device_id": f"eq.{device_id}",
                    "active": "eq.true",
                    "order": "created_at.asc,installation_id.asc",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de instalações inválida.")
            return tuple(
                self._push_installation_from_mapping(row)
                for row in data
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def claim_tracking_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        return self._push_boolean_rpc(
            "claim_vessel_tracking_delivery",
            {
                "p_event_id": str(event_id),
                "p_installation_id": str(installation_id),
                "p_lease_seconds": lease_seconds,
            },
            "claimed",
        )

    def set_tracking_push_delivery_status(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        status: TrackingPushDeliveryStatus,
    ) -> None:
        self._push_boolean_rpc(
            "set_vessel_tracking_delivery_status",
            {
                "p_event_id": str(event_id),
                "p_installation_id": str(installation_id),
                "p_status": status.value,
            },
            "updated",
        )

    def get_tracking_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
    ) -> TrackingPushDelivery | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/vessel_tracking_deliveries",
                headers=self._headers(),
                params={
                    "select": (
                        "event_id,installation_id,status,"
                        "claimed_at,updated_at"
                    ),
                    "event_id": f"eq.{event_id}",
                    "installation_id": f"eq.{installation_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de delivery inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de delivery inválida.")
            row = data[0]
            claimed_at = self._parse_datetime(row.get("claimed_at"))
            updated_at = self._parse_datetime(row.get("updated_at"))
            if claimed_at is None or updated_at is None:
                raise ValueError("Timestamp de delivery ausente.")
            return TrackingPushDelivery(
                event_id=UUID(str(row["event_id"])),
                installation_id=UUID(str(row["installation_id"])),
                status=TrackingPushDeliveryStatus(str(row["status"])),
                claimed_at=claimed_at,
                updated_at=updated_at,
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def claim_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        return self._push_boolean_rpc(
            "claim_push_delivery",
            {
                "p_event_id": str(event_id),
                "p_installation_id": str(installation_id),
                "p_lease_seconds": lease_seconds,
            },
            "claimed",
        )

    def set_push_delivery_status(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        status: PushDeliveryStatus,
    ) -> None:
        self._push_boolean_rpc(
            "set_push_delivery_status",
            {
                "p_event_id": str(event_id),
                "p_installation_id": str(installation_id),
                "p_status": status.value,
            },
            "updated",
        )

    def get_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
    ) -> PushDelivery | None:
        try:
            response = self._client.get(
                f"{self._base_url}/rest/v1/push_deliveries",
                headers=self._headers(),
                params={
                    "select": (
                        "event_id,installation_id,status,"
                        "claimed_at,updated_at"
                    ),
                    "event_id": f"eq.{event_id}",
                    "installation_id": f"eq.{installation_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta de delivery inválida.")
            if not data:
                return None
            if len(data) != 1 or not isinstance(data[0], dict):
                raise ValueError("Resposta de delivery inválida.")
            row = data[0]
            claimed_at = self._parse_datetime(row.get("claimed_at"))
            updated_at = self._parse_datetime(row.get("updated_at"))
            if claimed_at is None or updated_at is None:
                raise ValueError("Timestamps de delivery ausentes.")
            return PushDelivery(
                event_id=UUID(str(row["event_id"])),
                installation_id=UUID(str(row["installation_id"])),
                status=PushDeliveryStatus(str(row["status"])),
                claimed_at=claimed_at,
                updated_at=updated_at,
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def _push_installation_rpc(
        self,
        name: str,
        payload: dict[str, Any],
    ) -> PushInstallation | None:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/{name}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise TypeError("Resposta RPC de instalação inválida.")
            if not data:
                return None
            if len(data) != 1:
                raise ValueError("Resposta RPC de instalação inválida.")
            return self._push_installation_from_mapping(data[0])
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def _push_boolean_rpc(
        self,
        name: str,
        payload: dict[str, Any],
        field: str,
    ) -> bool:
        try:
            response = self._client.post(
                f"{self._base_url}/rest/v1/rpc/{name}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            row = self._extract_row(response.json())
            value = row[field]
            if not isinstance(value, bool):
                raise TypeError("Resposta booleana RPC inválida.")
            return value
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PersistenceUnavailableError() from exc

    def _push_installation_from_mapping(
        self,
        row: Any,
    ) -> PushInstallation:
        if not isinstance(row, dict):
            raise TypeError("Instalação persistida inválida.")
        push_enabled_at = self._parse_datetime(row.get("push_enabled_at"))
        last_seen_at = self._parse_datetime(row.get("last_seen_at"))
        last_foreground_at = self._parse_datetime(
            row.get("last_foreground_at")
        )
        created_at = self._parse_datetime(row.get("created_at"))
        updated_at = self._parse_datetime(row.get("updated_at"))
        if (
            push_enabled_at is None
            or last_seen_at is None
            or created_at is None
            or updated_at is None
        ):
            raise ValueError("Timestamps de instalação ausentes.")
        return PushInstallation(
            installation_id=UUID(str(row["installation_id"])),
            device_id=str(row["device_id"]),
            endpoint=None if row.get("endpoint") is None else str(row["endpoint"]),
            p256dh=None if row.get("p256dh") is None else str(row["p256dh"]),
            auth=None if row.get("auth") is None else str(row["auth"]),
            preferences=PushPreferences(
                confirmed=bool(row["pref_confirmed"]),
                updated=bool(row["pref_updated"]),
                completed=bool(row["pref_completed"]),
                cancelled=bool(row["pref_cancelled"]),
                anchored=bool(row["pref_anchored"]),
            ),
            push_enabled_at=push_enabled_at,
            last_seen_at=last_seen_at,
            last_foreground_at=last_foreground_at,
            active=bool(row["active"]),
            created_at=created_at,
            updated_at=updated_at,
        )
