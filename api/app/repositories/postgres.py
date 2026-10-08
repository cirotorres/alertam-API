from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.models.maneuver_event import ManeuverEventIn
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.cloud_bindings import (
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


class PostgresDeviceRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create_device(self, record: DeviceAuthRecord) -> None:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                conn.execute(
                    """
                    insert into public.devices (
                        device_id,
                        device_secret_hash,
                        view_secret_hash,
                        description,
                        enabled
                    )
                    values (%s, %s, %s, %s, %s)
                    """,
                    (
                        record.device_id,
                        record.device_secret_hash,
                        record.view_secret_hash,
                        record.description,
                        record.enabled,
                    ),
                )
        except UniqueViolation as exc:
            raise DeviceAlreadyExistsError(record.device_id) from exc
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

    def get_device_auth(
        self,
        device_id: str,
    ) -> DeviceAuthRecord | None:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select
                        device_id,
                        device_secret_hash,
                        view_secret_hash,
                        description,
                        enabled
                    from public.devices
                    where device_id = %s
                    """,
                    (device_id,),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        if row is None:
            return None
        return DeviceAuthRecord(
            device_id=str(row[0]),
            device_secret_hash=str(row[1]),
            view_secret_hash=None if row[2] is None else str(row[2]),
            description=None if row[3] is None else str(row[3]),
            enabled=bool(row[4]),
        )

    def ensure_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    insert into public.webpilot_auth_realms (realm_id, active)
                    values (%s, true)
                    on conflict (realm_id) do update
                    set realm_id = excluded.realm_id
                    returning realm_id, active, created_at, updated_at
                    """,
                    (realm_id,),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._webpilot_auth_realm_from_row(row)

    def get_webpilot_auth_realm(
        self,
        realm_id: str,
    ) -> WebPilotAuthRealmRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select realm_id, active, created_at, updated_at
                    from public.webpilot_auth_realms
                    where realm_id = %s
                    """,
                    (realm_id,),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._webpilot_auth_realm_from_row(row)

    def set_webpilot_auth_realm_active(
        self,
        realm_id: str,
        active: bool,
    ) -> WebPilotAuthRealmRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select realm_id, active, created_at, updated_at
                    from public.set_webpilot_auth_realm_active(%s, %s)
                    """,
                    (realm_id, active),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._webpilot_auth_realm_from_row(row)

    def authorize_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        return self._realm_device_rpc(
            "authorize_realm_device",
            realm_id,
            device_id,
        )

    def revoke_realm_device(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        return self._realm_device_rpc(
            "revoke_realm_device",
            realm_id,
            device_id,
        )

    def get_realm_device_authorization(
        self,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select realm_id, device_id, authorized_at, revoked_at
                    from public.webpilot_auth_realm_devices
                    where realm_id = %s and device_id = %s
                    """,
                    (realm_id, device_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._realm_device_authorization_from_row(row)

    def get_active_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select cloud_binding_id, device_id, realm_id,
                           credential_hash, credential_version, status,
                           created_at, updated_at, revoked_at
                    from public.cloud_bindings
                    where device_id = %s and status = 'active'
                    """,
                    (device_id,),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._cloud_binding_from_row(row)

    def list_cloud_bindings(
        self,
        device_id: str,
    ) -> tuple[CloudBindingRecord, ...]:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(
                    """
                    select cloud_binding_id, device_id, realm_id,
                           credential_hash, credential_version, status,
                           created_at, updated_at, revoked_at
                    from public.cloud_bindings
                    where device_id = %s
                    order by lifecycle_order
                    """,
                    (device_id,),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return tuple(
            item
            for row in rows
            if (item := self._cloud_binding_from_row(row)) is not None
        )

    def ensure_cloud_binding(
        self,
        device_id: str,
        realm_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None:
        try:
            return self._cloud_binding_rpc(
                "ensure_cloud_binding",
                (device_id, realm_id, credential_hash),
            )
        except psycopg.errors.RaiseException as exc:
            if "cloud_binding_conflict" in str(exc):
                raise CloudBindingConflictError(device_id) from exc
            raise PersistenceUnavailableError() from exc

    def rotate_cloud_binding(
        self,
        device_id: str,
        credential_hash: str,
    ) -> CloudBindingRecord | None:
        return self._cloud_binding_rpc(
            "rotate_cloud_binding",
            (device_id, credential_hash),
        )

    def revoke_cloud_binding(
        self,
        device_id: str,
    ) -> CloudBindingRecord | None:
        return self._cloud_binding_rpc(
            "revoke_cloud_binding",
            (device_id,),
        )

    def _realm_device_rpc(
        self,
        name: str,
        realm_id: str,
        device_id: str,
    ) -> RealmDeviceAuthorizationRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    f"""
                    select realm_id, device_id, authorized_at, revoked_at
                    from public.{name}(%s, %s)
                    """,
                    (realm_id, device_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._realm_device_authorization_from_row(row)

    def _cloud_binding_rpc(
        self,
        name: str,
        params: tuple[Any, ...],
    ) -> CloudBindingRecord | None:
        placeholders = ", ".join(["%s"] * len(params))
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    f"""
                    select cloud_binding_id, device_id, realm_id,
                           credential_hash, credential_version, status,
                           created_at, updated_at, revoked_at
                    from public.{name}({placeholders})
                    """,
                    params,
                ).fetchone()
        except psycopg.errors.RaiseException:
            raise
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._cloud_binding_from_row(row)

    @classmethod
    def _webpilot_auth_realm_from_row(
        cls,
        row: Any,
    ) -> WebPilotAuthRealmRecord | None:
        if row is None:
            return None
        try:
            return WebPilotAuthRealmRecord(
                realm_id=str(row[0]),
                active=bool(row[1]),
                created_at=cls._aware_datetime(row[2]),
                updated_at=cls._aware_datetime(row[3]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    @classmethod
    def _realm_device_authorization_from_row(
        cls,
        row: Any,
    ) -> RealmDeviceAuthorizationRecord | None:
        if row is None:
            return None
        try:
            return RealmDeviceAuthorizationRecord(
                realm_id=str(row[0]),
                device_id=str(row[1]),
                authorized_at=cls._aware_datetime(row[2]),
                revoked_at=None if row[3] is None else cls._aware_datetime(row[3]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    @classmethod
    def _cloud_binding_from_row(
        cls,
        row: Any,
    ) -> CloudBindingRecord | None:
        if row is None:
            return None
        try:
            return CloudBindingRecord(
                cloud_binding_id=UUID(str(row[0])),
                device_id=str(row[1]),
                realm_id=str(row[2]),
                credential_hash=str(row[3]),
                credential_version=int(row[4]),
                status=CloudBindingStatus(str(row[5])),
                created_at=cls._aware_datetime(row[6]),
                updated_at=cls._aware_datetime(row[7]),
                revoked_at=None if row[8] is None else cls._aware_datetime(row[8]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def ensure_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str = "other",
        display_code: str | None = None,
    ) -> MobileInstallationRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select installation_id, device_id, active,
                           created_at, last_seen_at, revoked_at,
                           platform, display_code
                    from public.ensure_mobile_installation(%s, %s, %s, %s)
                    """,
                    (device_id, installation_id, platform, display_code),
                ).fetchone()
        except UniqueViolation as exc:
            constraint = getattr(
                getattr(exc, "diag", None),
                "constraint_name",
                None,
            )
            if (
                constraint == "mobile_installations_display_code_unique"
                or "mobile_installations_display_code_unique" in str(exc)
            ):
                raise MobileInstallationDisplayCodeConflictError() from exc
            raise PersistenceUnavailableError() from exc
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._mobile_installation_from_row(row)

    def get_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> MobileInstallationRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select installation_id, device_id, active,
                           created_at, last_seen_at, revoked_at,
                           platform, display_code
                    from public.mobile_installations
                    where device_id = %s and installation_id = %s
                    """,
                    (device_id, installation_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._mobile_installation_from_row(row)

    def list_mobile_installations(
        self,
        device_id: str,
        *,
        revoked_since: datetime,
    ) -> tuple[MobileInstallationRecord, ...]:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(
                    """
                    select installation_id, device_id, active,
                           created_at, last_seen_at, revoked_at,
                           platform, display_code
                    from public.list_mobile_installations(%s, %s)
                    """,
                    (device_id, revoked_since),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return tuple(
            item
            for row in rows
            if (item := self._mobile_installation_from_row(row)) is not None
        )

    def touch_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
        *,
        platform: str,
    ) -> MobileInstallationRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select installation_id, device_id, active,
                           created_at, last_seen_at, revoked_at,
                           platform, display_code
                    from public.touch_mobile_installation(%s, %s, %s)
                    """,
                    (device_id, installation_id, platform),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._mobile_installation_from_row(row)

    def revoke_mobile_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select updated
                    from public.revoke_mobile_installation(%s, %s)
                    """,
                    (device_id, installation_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None or not isinstance(row[0], bool):
            raise PersistenceUnavailableError()
        return row[0]

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
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select installation_id, device_id, active,
                           created_at, last_seen_at, revoked_at,
                           platform, display_code
                    from public.switch_mobile_installation(
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        switch_id,
                        from_device_id,
                        from_installation_id,
                        to_device_id,
                        to_installation_id,
                        platform,
                        display_code,
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            constraint = getattr(
                getattr(exc, "diag", None),
                "constraint_name",
                None,
            )
            if (
                constraint == "mobile_installations_display_code_unique"
                or "mobile_installations_display_code_unique" in str(exc)
            ):
                raise MobileInstallationDisplayCodeConflictError() from exc
            raise PersistenceUnavailableError() from exc
        except psycopg.errors.RaiseException as exc:
            if "mobile_session_switch_conflict" in str(exc):
                raise MobileInstallationSwitchConflictError() from exc
            raise PersistenceUnavailableError() from exc
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._mobile_installation_from_row(row)

    @classmethod
    def _mobile_installation_from_row(
        cls,
        row: Any,
    ) -> MobileInstallationRecord | None:
        if row is None:
            return None
        try:
            return MobileInstallationRecord(
                installation_id=UUID(str(row[0])),
                device_id=str(row[1]),
                active=bool(row[2]),
                created_at=cls._aware_datetime(row[3]),
                last_seen_at=cls._aware_datetime(row[4]),
                revoked_at=(
                    None
                    if row[5] is None
                    else cls._aware_datetime(row[5])
                ),
                platform=str(row[6]),
                display_code=str(row[7]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def get_snapshot(
        self,
        device_id: str,
    ) -> StoredSnapshot | None:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select
                        device_id,
                        snapshot,
                        snapshot_schema_version,
                        boot_id,
                        sequence,
                        generated_at,
                        received_at
                    from public.devices
                    where device_id = %s
                    """,
                    (device_id,),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        if row is None or row[1] is None:
            return None

        snapshot = row[1]
        if not isinstance(snapshot, dict):
            raise PersistenceUnavailableError()

        try:
            return StoredSnapshot(
                device_id=str(row[0]),
                snapshot=snapshot,
                snapshot_schema_version=int(row[2]),
                boot_id=UUID(str(row[3])),
                sequence=int(row[4]),
                generated_at=self._aware_datetime(row[5]),
                received_at=self._aware_datetime(row[6]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def replace_mobile_pairing_code(
        self,
        device_id: str,
        code_hash: str,
        *,
        expires_at: datetime,
    ) -> bool:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select updated
                    from public.replace_mobile_pairing_code(%s, %s, %s)
                    """,
                    (device_id, code_hash, expires_at),
                ).fetchone()
        except UniqueViolation as exc:
            raise MobilePairingCodeConflictError() from exc
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None or not isinstance(row[0], bool):
            raise PersistenceUnavailableError()
        return row[0]

    def redeem_mobile_pairing_code(
        self,
        code_hash: str,
        ticket_hash: str,
        *,
        ticket_expires_at: datetime,
        now: datetime,
    ) -> MobilePairingCodeRedeemResult:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select status, device_id, ticket_expires_at
                    from public.redeem_mobile_pairing_code(%s, %s, %s, %s)
                    """,
                    (code_hash, ticket_hash, ticket_expires_at, now),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None:
            raise PersistenceUnavailableError()
        try:
            status = MobilePairingCodeRedeemStatus(str(row[0]))
            expires = (
                None
                if row[2] is None
                else self._aware_datetime(row[2])
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc
        return MobilePairingCodeRedeemResult(
            status=status,
            device_id=None if row[1] is None else str(row[1]),
            ticket_expires_at=expires,
        )

    def validate_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        *,
        now: datetime,
    ) -> bool:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select valid
                    from public.validate_mobile_pairing_ticket(%s, %s, %s)
                    """,
                    (device_id, ticket_hash, now),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None or not isinstance(row[0], bool):
            raise PersistenceUnavailableError()
        return row[0]

    def consume_mobile_pairing_ticket(
        self,
        device_id: str,
        ticket_hash: str,
        purpose: str,
        *,
        now: datetime,
    ) -> bool:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select valid
                    from public.consume_mobile_pairing_ticket(
                        %s, %s, %s, %s
                    )
                    """,
                    (device_id, ticket_hash, purpose, now),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None or not isinstance(row[0], bool):
            raise PersistenceUnavailableError()
        return row[0]

    def rotate_view_secret_hash(
        self,
        device_id: str,
        view_secret_hash: str,
    ) -> bool:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select updated
                    from public.rotate_device_view_secret(%s, %s)
                    """,
                    (device_id, view_secret_hash),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        if row is None or not isinstance(row[0], bool):
            raise PersistenceUnavailableError()
        return row[0]

    def accept_snapshot_atomic(
        self,
        candidate: SnapshotCandidate,
    ) -> AcceptSnapshotResult:
        try:
            with psycopg.connect(
                self._database_url,
                autocommit=True,
            ) as conn:
                row = conn.execute(
                    """
                    select status, received_at
                    from public.accept_device_snapshot(
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        candidate.device_id,
                        Jsonb(candidate.snapshot),
                        candidate.snapshot_schema_version,
                        candidate.boot_id,
                        candidate.sequence,
                        candidate.generated_at,
                    ),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        if row is None:
            raise PersistenceUnavailableError()

        try:
            status = AcceptSnapshotStatus(str(row[0]))
            received_at = (
                None
                if row[1] is None
                else self._aware_datetime(row[1])
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

        return AcceptSnapshotResult(
            status=status,
            received_at=received_at,
        )

    @staticmethod
    def _aware_datetime(value: Any) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError("Timestamp PostgreSQL inválido.")
        return value

    def accept_maneuver_event_atomic(
        self,
        device_id: str,
        event: ManeuverEventIn,
    ) -> AcceptEventResult:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select status, ingestion_id, ingested_at, event_payload
                    from public.accept_maneuver_event(%s, %s)
                    """,
                    (device_id, Jsonb(event.canonical_payload())),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        if row is None:
            raise PersistenceUnavailableError()
        try:
            status = AcceptEventStatus(str(row[0]))
            stored = None
            if row[1] is not None:
                stored = StoredManeuverEvent(
                    ingestion_id=int(row[1]),
                    device_id=device_id,
                    event=ManeuverEventIn.model_validate(row[3]),
                    ingested_at=self._aware_datetime(row[2]),
                )
        except (TypeError, ValueError) as exc:
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
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                tracking_rows = conn.execute(
                    """
                    select event_payload
                    from public.vessel_tracking_events
                    where device_id = %s
                    order by ingestion_id desc
                    """,
                    (device_id,),
                ).fetchall()
                maneuver_rows = conn.execute(
                    """
                    select event_payload
                    from public.maneuver_events
                    where device_id = %s
                    order by ingestion_id desc
                    """,
                    (device_id,),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        for row in tracking_rows:
            try:
                event = VesselTrackingEventIn.model_validate(row[0])
            except (TypeError, ValueError):
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
            try:
                event = ManeuverEventIn.model_validate(row[0])
            except (TypeError, ValueError):
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
    def _tracked_vessel_from_row(
        cls,
        row: Any,
    ) -> TrackedVesselRecord | None:
        if row is None:
            return None
        try:
            current = row[10]
            if current is not None and not isinstance(current, dict):
                raise TypeError("current inválido")
            return TrackedVesselRecord(
                tracked_vessel_id=UUID(str(row[0])),
                device_id=str(row[1]),
                installation_id=UUID(str(row[2])),
                vessel_identity=str(row[3]),
                vessel_imo=None if row[4] is None else str(row[4]),
                vessel_name=str(row[5]),
                started_at=cls._aware_datetime(row[6]),
                active=bool(row[7]),
                stopped_at=(
                    None if row[8] is None else cls._aware_datetime(row[8])
                ),
                last_seen_at=(
                    None if row[9] is None else cls._aware_datetime(row[9])
                ),
                current=current,
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def upsert_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        evidence: VesselEvidence,
    ) -> TrackedVesselRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select tracked_vessel_id, device_id, installation_id,
                           vessel_identity, vessel_imo, vessel_name,
                           started_at, active, stopped_at, last_seen_at, current
                    from public.upsert_tracked_vessel(
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        device_id,
                        installation_id,
                        evidence.vessel_identity,
                        evidence.vessel_imo,
                        evidence.vessel_name,
                        Jsonb(evidence.current) if evidence.current is not None else None,
                        evidence.observed_at,
                    ),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._tracked_vessel_from_row(row)

    def list_tracked_vessels(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> tuple[TrackedVesselRecord, ...]:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(
                    """
                    select tracked_vessel_id, device_id, installation_id,
                           vessel_identity, vessel_imo, vessel_name,
                           started_at, active, stopped_at, last_seen_at, current
                    from public.tracked_vessels
                    where device_id = %s
                      and installation_id = %s
                      and active = true
                    order by started_at asc
                    """,
                    (device_id, installation_id),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return tuple(
            item
            for row in rows
            if (item := self._tracked_vessel_from_row(row)) is not None
        )

    def get_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select tracked_vessel_id, device_id, installation_id,
                           vessel_identity, vessel_imo, vessel_name,
                           started_at, active, stopped_at, last_seen_at, current
                    from public.tracked_vessels
                    where device_id = %s
                      and installation_id = %s
                      and tracked_vessel_id = %s
                    """,
                    (device_id, installation_id, tracked_vessel_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._tracked_vessel_from_row(row)

    def deactivate_tracked_vessel(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> TrackedVesselRecord | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select tracked_vessel_id, device_id, installation_id,
                           vessel_identity, vessel_imo, vessel_name,
                           started_at, active, stopped_at, last_seen_at, current
                    from public.deactivate_tracked_vessel(%s, %s, %s)
                    """,
                    (device_id, installation_id, tracked_vessel_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._tracked_vessel_from_row(row)

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
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select public.project_tracked_vessels(
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        device_id,
                        vessel_identity,
                        vessel_imo,
                        vessel_name,
                        observed_at,
                        replace_current,
                        Jsonb(current) if current is not None else None,
                        Jsonb(patch) if patch is not None else None,
                    ),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None:
            raise PersistenceUnavailableError()
        try:
            return int(row[0])
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def list_tracked_vessel_event_records(
        self,
        device_id: str,
        installation_id: UUID,
        tracked_vessel_id: UUID,
    ) -> tuple[VesselEventRecord, ...]:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(
                    """
                    select kind, ingestion_id, ingested_at, event_payload
                    from public.list_tracked_vessel_timeline(%s, %s, %s)
                    """,
                    (device_id, installation_id, tracked_vessel_id),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        result: list[VesselEventRecord] = []
        try:
            for row in rows:
                kind = str(row[0])
                payload = row[3]
                if kind == "MANEUVER":
                    event = ManeuverEventIn.model_validate(payload)
                elif kind == "TRACKING":
                    event = VesselTrackingEventIn.model_validate(payload)
                else:
                    raise ValueError("kind inválido")
                result.append(VesselEventRecord(
                    kind=kind,
                    ingestion_id=int(row[1]),
                    ingested_at=self._aware_datetime(row[2]),
                    event=event,
                ))
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc
        return tuple(result)

    def latest_tracking_event_cursor(
        self,
        device_id: str,
    ) -> int | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select max(ingestion_id)
                    from public.vessel_tracking_events
                    where device_id = %s
                    """,
                    (device_id,),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None or row[0] is None:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError) as exc:
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
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(
                    """
                    select tracked_vessel_id, ingestion_id,
                           ingested_at, event_payload
                    from public.list_installation_tracking_events(
                        %s, %s, %s, %s
                    )
                    """,
                    (device_id, installation_id, after, limit),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        result: list[InstallationTrackingEventRecord] = []
        try:
            for row in rows:
                event = VesselTrackingEventIn.model_validate(row[3])
                stored = StoredVesselTrackingEvent(
                    ingestion_id=int(row[1]),
                    device_id=device_id,
                    event=event,
                    ingested_at=self._aware_datetime(row[2]),
                )
                result.append(InstallationTrackingEventRecord(
                    tracked_vessel_id=UUID(str(row[0])),
                    stored=stored,
                ))
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc
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
        normalized_name = " ".join(vessel_name.upper().split())
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                if vessel_imo is not None:
                    row = conn.execute(
                        """
                        select tracked_vessel_id, device_id, installation_id,
                               vessel_identity, vessel_imo, vessel_name,
                               started_at, active, stopped_at, last_seen_at, current
                        from public.tracked_vessels
                        where device_id = %s
                          and installation_id = %s
                          and active = true
                          and started_at <= %s
                          and (
                              vessel_identity = %s
                              or vessel_imo = %s
                              or (
                                  vessel_imo is null
                                  and regexp_replace(
                                      upper(trim(vessel_name)),
                                      '[[:space:]]+',
                                      ' ',
                                      'g'
                                  ) = %s
                              )
                          )
                        order by started_at asc
                        limit 1
                        """,
                        (
                            device_id,
                            installation_id,
                            occurred_at,
                            vessel_identity,
                            vessel_imo,
                            normalized_name,
                        ),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        select tracked_vessel_id, device_id, installation_id,
                               vessel_identity, vessel_imo, vessel_name,
                               started_at, active, stopped_at, last_seen_at, current
                        from public.tracked_vessels
                        where device_id = %s
                          and installation_id = %s
                          and active = true
                          and started_at <= %s
                          and (
                              vessel_identity = %s
                              or (
                                  vessel_imo is null
                                  and regexp_replace(
                                      upper(trim(vessel_name)),
                                      '[[:space:]]+',
                                      ' ',
                                      'g'
                                  ) = %s
                              )
                          )
                        order by started_at asc
                        limit 1
                        """,
                        (
                            device_id,
                            installation_id,
                            occurred_at,
                            vessel_identity,
                            normalized_name,
                        ),
                    ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return self._tracked_vessel_from_row(row)

    def accept_vessel_tracking_event_atomic(
        self,
        device_id: str,
        event: VesselTrackingEventIn,
    ) -> AcceptTrackingEventResult:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select status, ingestion_id, ingested_at, event_payload
                    from public.accept_vessel_tracking_event(%s, %s)
                    """,
                    (device_id, Jsonb(event.canonical_payload())),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        if row is None:
            raise PersistenceUnavailableError()
        try:
            status = AcceptTrackingEventStatus(str(row[0]))
            stored = None
            if row[1] is not None:
                stored = StoredVesselTrackingEvent(
                    ingestion_id=int(row[1]),
                    device_id=device_id,
                    event=VesselTrackingEventIn.model_validate(row[3]),
                    ingested_at=self._aware_datetime(row[2]),
                )
        except (TypeError, ValueError) as exc:
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

        params: tuple[Any, ...]
        if after is not None:
            sql = """
                select ingestion_id, device_id, event_payload, ingested_at
                from public.maneuver_events
                where device_id = %s and ingestion_id > %s
                order by ingestion_id asc
                limit %s
            """
            params = (device_id, after, limit)
            descending = False
        elif before is not None:
            sql = """
                select ingestion_id, device_id, event_payload, ingested_at
                from public.maneuver_events
                where device_id = %s and ingestion_id < %s
                order by ingestion_id desc
                limit %s
            """
            params = (device_id, before, limit + 1)
            descending = True
        else:
            sql = """
                select ingestion_id, device_id, event_payload, ingested_at
                from public.maneuver_events
                where device_id = %s
                order by ingestion_id desc
                limit %s
            """
            params = (device_id, limit + 1)
            descending = True

        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(sql, params).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        has_more_before = descending and len(rows) > limit
        rows = rows[:limit]
        if descending:
            rows = list(reversed(rows))
        try:
            events = tuple(
                StoredManeuverEvent(
                    ingestion_id=int(row[0]),
                    device_id=str(row[1]),
                    event=ManeuverEventIn.model_validate(row[2]),
                    ingested_at=self._aware_datetime(row[3]),
                )
                for row in rows
            )
        except (TypeError, ValueError) as exc:
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
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                selected = conn.execute(
                    """
                    select maneuver_id
                    from public.maneuver_events
                    where device_id = %s and event_id = %s
                    """,
                    (device_id, event_id),
                ).fetchone()
                if selected is None:
                    return None
                maneuver_id = UUID(str(selected[0]))
                rows = conn.execute(
                    """
                    select ingestion_id, device_id, event_payload, ingested_at
                    from public.maneuver_events
                    where device_id = %s and maneuver_id = %s
                    order by ingestion_id asc
                    """,
                    (device_id, maneuver_id),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

        try:
            events = tuple(
                StoredManeuverEvent(
                    ingestion_id=int(row[0]),
                    device_id=str(row[1]),
                    event=ManeuverEventIn.model_validate(row[2]),
                    ingested_at=self._aware_datetime(row[3]),
                )
                for row in rows
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

        if not events or not any(
            item.event.event_id == event_id for item in events
        ):
            return None

        return ManeuverEventDetail(
            selected_event_id=event_id,
            maneuver_id=maneuver_id,
            events=events,
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
        row = self._call_push_row_rpc(
            """
            select
                installation_id, device_id, endpoint, p256dh, auth,
                pref_confirmed, pref_updated, pref_completed,
                pref_cancelled, pref_anchored, push_enabled_at,
                last_seen_at, last_foreground_at, active,
                created_at, updated_at
            from public.upsert_push_installation(
                %s, %s, %s, %s, %s
            )
            """,
            (device_id, installation_id, endpoint, p256dh, auth),
        )
        return None if row is None else self._push_installation_from_row(row)

    def get_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select
                        installation_id, device_id, endpoint, p256dh, auth,
                        pref_confirmed, pref_updated, pref_completed,
                        pref_cancelled, pref_anchored, push_enabled_at,
                        last_seen_at, last_foreground_at, active,
                        created_at, updated_at
                    from public.push_installations
                    where device_id = %s and installation_id = %s
                    """,
                    (device_id, installation_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return None if row is None else self._push_installation_from_row(row)

    def update_push_preferences(
        self,
        device_id: str,
        installation_id: UUID,
        preferences: PushPreferences,
    ) -> PushInstallation | None:
        row = self._call_push_row_rpc(
            """
            select
                installation_id, device_id, endpoint, p256dh, auth,
                pref_confirmed, pref_updated, pref_completed,
                pref_cancelled, pref_anchored, push_enabled_at,
                last_seen_at, last_foreground_at, active,
                created_at, updated_at
            from public.update_push_preferences(
                %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                device_id,
                installation_id,
                preferences.confirmed,
                preferences.updated,
                preferences.completed,
                preferences.cancelled,
                preferences.anchored,
            ),
        )
        return None if row is None else self._push_installation_from_row(row)

    def touch_push_foreground(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None:
        row = self._call_push_row_rpc(
            """
            select
                installation_id, device_id, endpoint, p256dh, auth,
                pref_confirmed, pref_updated, pref_completed,
                pref_cancelled, pref_anchored, push_enabled_at,
                last_seen_at, last_foreground_at, active,
                created_at, updated_at
            from public.touch_push_foreground(%s, %s)
            """,
            (device_id, installation_id),
        )
        return None if row is None else self._push_installation_from_row(row)

    def deactivate_push_installation(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> bool:
        return self._call_boolean_rpc(
            "select updated from public.deactivate_push_installation(%s, %s)",
            (device_id, installation_id),
            "updated",
        )

    def list_active_push_installations(
        self,
        device_id: str,
    ) -> tuple[PushInstallation, ...]:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                rows = conn.execute(
                    """
                    select
                        installation_id, device_id, endpoint, p256dh, auth,
                        pref_confirmed, pref_updated, pref_completed,
                        pref_cancelled, pref_anchored, push_enabled_at,
                        last_seen_at, last_foreground_at, active,
                        created_at, updated_at
                    from public.push_installations
                    where device_id = %s and active = true
                    order by created_at, installation_id
                    """,
                    (device_id,),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return tuple(self._push_installation_from_row(row) for row in rows)

    def claim_tracking_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        return self._call_boolean_rpc(
            """
            select claimed
            from public.claim_vessel_tracking_delivery(%s, %s, %s)
            """,
            (event_id, installation_id, lease_seconds),
            "claimed",
        )

    def set_tracking_push_delivery_status(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        status: TrackingPushDeliveryStatus,
    ) -> None:
        self._call_boolean_rpc(
            """
            select updated
            from public.set_vessel_tracking_delivery_status(%s, %s, %s)
            """,
            (event_id, installation_id, status.value),
            "updated",
        )

    def get_tracking_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
    ) -> TrackingPushDelivery | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select event_id, installation_id, status,
                           claimed_at, updated_at
                    from public.vessel_tracking_deliveries
                    where event_id = %s and installation_id = %s
                    """,
                    (event_id, installation_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None:
            return None
        try:
            return TrackingPushDelivery(
                event_id=UUID(str(row[0])),
                installation_id=UUID(str(row[1])),
                status=TrackingPushDeliveryStatus(str(row[2])),
                claimed_at=self._aware_datetime(row[3]),
                updated_at=self._aware_datetime(row[4]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def claim_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        *,
        lease_seconds: int = 8,
    ) -> bool:
        return self._call_boolean_rpc(
            "select claimed from public.claim_push_delivery(%s, %s, %s)",
            (UUID(str(event_id)), installation_id, lease_seconds),
            "claimed",
        )

    def set_push_delivery_status(
        self,
        event_id: str | UUID,
        installation_id: UUID,
        status: PushDeliveryStatus,
    ) -> None:
        self._call_boolean_rpc(
            "select updated from public.set_push_delivery_status(%s, %s, %s)",
            (UUID(str(event_id)), installation_id, status.value),
            "updated",
        )

    def get_push_delivery(
        self,
        event_id: str | UUID,
        installation_id: UUID,
    ) -> PushDelivery | None:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(
                    """
                    select
                        event_id, installation_id, status,
                        claimed_at, updated_at
                    from public.push_deliveries
                    where event_id = %s and installation_id = %s
                    """,
                    (UUID(str(event_id)), installation_id),
                ).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None:
            return None
        try:
            return PushDelivery(
                event_id=UUID(str(row[0])),
                installation_id=UUID(str(row[1])),
                status=PushDeliveryStatus(str(row[2])),
                claimed_at=self._aware_datetime(row[3]),
                updated_at=self._aware_datetime(row[4]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc

    def _call_push_row_rpc(
        self,
        sql: str,
        params: tuple[Any, ...],
    ):
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                return conn.execute(sql, params).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc

    def _call_boolean_rpc(
        self,
        sql: str,
        params: tuple[Any, ...],
        _field: str,
    ) -> bool:
        try:
            with psycopg.connect(self._database_url, autocommit=True) as conn:
                row = conn.execute(sql, params).fetchone()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        if row is None or not isinstance(row[0], bool):
            raise PersistenceUnavailableError()
        return row[0]

    def _push_installation_from_row(self, row: Any) -> PushInstallation:
        try:
            return PushInstallation(
                installation_id=UUID(str(row[0])),
                device_id=str(row[1]),
                endpoint=None if row[2] is None else str(row[2]),
                p256dh=None if row[3] is None else str(row[3]),
                auth=None if row[4] is None else str(row[4]),
                preferences=PushPreferences(
                    confirmed=bool(row[5]),
                    updated=bool(row[6]),
                    completed=bool(row[7]),
                    cancelled=bool(row[8]),
                    anchored=bool(row[9]),
                ),
                push_enabled_at=self._aware_datetime(row[10]),
                last_seen_at=self._aware_datetime(row[11]),
                last_foreground_at=(
                    None if row[12] is None else self._aware_datetime(row[12])
                ),
                active=bool(row[13]),
                created_at=self._aware_datetime(row[14]),
                updated_at=self._aware_datetime(row[15]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc
