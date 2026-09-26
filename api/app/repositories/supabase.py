from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    PersistenceUnavailableError,
    SnapshotCandidate,
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
