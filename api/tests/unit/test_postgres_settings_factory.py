from __future__ import annotations

import pytest

from app.core.config import Settings
from app.repositories.factory import create_devices_repository
from app.repositories.postgres import PostgresDeviceRepository


def test_postgres_backend_requires_database_url():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            _env_file=None,
            environment="development",
            persistence_backend="postgres",
            database_url="",
        )


def test_postgres_backend_is_allowed_for_development():
    settings = Settings(
        _env_file=None,
        environment="development",
        persistence_backend="postgres",
        database_url="postgresql://user:pass@db:5432/alertam_dev",
    )

    repository = create_devices_repository(settings)

    assert isinstance(repository, PostgresDeviceRepository)


def test_production_accepts_only_supabase_backend():
    with pytest.raises(ValueError, match="produção"):
        Settings(
            _env_file=None,
            environment="production",
            persistence_backend="postgres",
            database_url="postgresql://user:pass@db:5432/alertam_prod",
        )
