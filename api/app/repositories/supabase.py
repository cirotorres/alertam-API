from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAuthRecord,
    PersistenceUnavailableError,
    SnapshotCandidate,
    StoredSnapshot,
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
