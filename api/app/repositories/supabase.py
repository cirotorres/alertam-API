from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.models.maneuver_event import ManeuverEventIn
from app.models.vessel_tracking_event import VesselTrackingEventIn
from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAuthRecord,
    MobileInstallationDisplayCodeConflictError,
    MobileInstallationRecord,
    MobileInstallationSwitchConflictError,
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
                        "device_id,device_secret_hash,view_secret_hash"
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
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
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
            ),
            push_enabled_at=push_enabled_at,
            last_seen_at=last_seen_at,
            last_foreground_at=last_foreground_at,
            active=bool(row["active"]),
            created_at=created_at,
            updated_at=updated_at,
        )
