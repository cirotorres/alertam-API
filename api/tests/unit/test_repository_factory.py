from __future__ import annotations

import pytest

from app.core.config import Settings
from app.repositories.memory import MemoryDeviceRepository
from app.repositories.supabase import SupabaseDeviceRepository
from app.repositories.factory import create_devices_repository
from app.security.credentials import verify_secret


def test_production_rejects_memory_persistence():
    with pytest.raises(ValueError, match="produção"):
        Settings(
            _env_file=None,
            environment="production",
            persistence_backend="memory",
        )


def test_memory_factory_can_seed_local_device_from_settings():
    settings = Settings(
        _env_file=None,
        environment="development",
        persistence_backend="memory",
        mock_seed_device=True,
        mock_device_id="pecem-01",
        mock_device_secret="device-secret",
        mock_view_secret="V" * 43,
    )

    repo = create_devices_repository(settings)

    assert isinstance(repo, MemoryDeviceRepository)
    record = repo.get_device_auth("pecem-01")
    assert record is not None
    assert verify_secret("device-secret", record.device_secret_hash)
    assert verify_secret("V" * 43, record.view_secret_hash)


def test_supabase_factory_builds_server_repository_without_network():
    settings = Settings(
        _env_file=None,
        environment="production",
        persistence_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    repo = create_devices_repository(settings)

    assert isinstance(repo, SupabaseDeviceRepository)

def test_production_app_can_be_built_without_opening_network_connection():
    from fastapi import FastAPI

    from app.main import create_app

    settings = Settings(
        _env_file=None,
        environment="production",
        persistence_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_secret_key="sb_secret_test",
    )

    application = create_app(settings=settings)

    assert isinstance(application, FastAPI)
