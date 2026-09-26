from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    PersistenceUnavailableError,
    SnapshotCandidate,
    StoredSnapshot,
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
                        view_secret_hash
                    )
                    values (%s, %s, %s)
                    """,
                    (
                        record.device_id,
                        record.device_secret_hash,
                        record.view_secret_hash,
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
                        view_secret_hash
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
        )

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
