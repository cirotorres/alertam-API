from __future__ import annotations

from app.core.config import Settings
from app.repositories.devices import DeviceAuthRecord
from app.repositories.events import AlertaRepository
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.postgres import PostgresDeviceRepository
from app.repositories.supabase import SupabaseDeviceRepository
from app.security.credentials import hash_secret


def create_devices_repository(settings: Settings) -> AlertaRepository:
    if settings.persistence_backend == "supabase":
        return SupabaseDeviceRepository(
            settings.supabase_url,
            settings.supabase_server_key,
        )

    if settings.persistence_backend == "postgres":
        return PostgresDeviceRepository(settings.database_url)

    repository = MemoryDeviceRepository()
    if settings.mock_seed_device:
        repository.create_device(
            DeviceAuthRecord(
                device_id=settings.mock_device_id,
                device_secret_hash=hash_secret(
                    settings.mock_device_secret
                ),
                view_secret_hash=(
                    hash_secret(settings.mock_view_secret)
                    if settings.mock_view_secret
                    else None
                ),
            )
        )
    return repository
