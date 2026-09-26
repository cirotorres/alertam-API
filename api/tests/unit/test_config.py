from __future__ import annotations

import pytest

from app.core.config import Settings


def test_memory_backend_does_not_require_supabase_credentials(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "memory")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.persistence_backend == "memory"
    assert settings.stale_after_seconds == 120
    assert settings.supabase_url == ""
    assert settings.supabase_service_role_key == ""


def test_supabase_backend_requires_server_credentials(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(ValueError, match="SUPABASE_URL"):
        Settings(_env_file=None)

def test_supabase_backend_accepts_current_secret_key(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_test")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.supabase_server_key == "sb_secret_test"


def test_supabase_backend_still_accepts_legacy_service_role_key(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "legacy-service-role")

    settings = Settings(_env_file=None)

    assert settings.supabase_server_key == "legacy-service-role"
