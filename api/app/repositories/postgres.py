from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.models.maneuver_event import ManeuverEventIn
from app.repositories.devices import (
    AcceptSnapshotResult,
    AcceptSnapshotStatus,
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
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
            select * from public.upsert_push_installation(
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
                        pref_cancelled, push_enabled_at, last_seen_at,
                        last_foreground_at, active, created_at, updated_at
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
            select * from public.update_push_preferences(
                %s, %s, %s, %s, %s, %s
            )
            """,
            (
                device_id,
                installation_id,
                preferences.confirmed,
                preferences.updated,
                preferences.completed,
                preferences.cancelled,
            ),
        )
        return None if row is None else self._push_installation_from_row(row)

    def touch_push_foreground(
        self,
        device_id: str,
        installation_id: UUID,
    ) -> PushInstallation | None:
        row = self._call_push_row_rpc(
            "select * from public.touch_push_foreground(%s, %s)",
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
                        pref_cancelled, push_enabled_at, last_seen_at,
                        last_foreground_at, active, created_at, updated_at
                    from public.push_installations
                    where device_id = %s and active = true
                    order by created_at, installation_id
                    """,
                    (device_id,),
                ).fetchall()
        except psycopg.Error as exc:
            raise PersistenceUnavailableError() from exc
        return tuple(self._push_installation_from_row(row) for row in rows)

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
                ),
                push_enabled_at=self._aware_datetime(row[9]),
                last_seen_at=self._aware_datetime(row[10]),
                last_foreground_at=(
                    None if row[11] is None else self._aware_datetime(row[11])
                ),
                active=bool(row[12]),
                created_at=self._aware_datetime(row[13]),
                updated_at=self._aware_datetime(row[14]),
            )
        except (TypeError, ValueError) as exc:
            raise PersistenceUnavailableError() from exc
