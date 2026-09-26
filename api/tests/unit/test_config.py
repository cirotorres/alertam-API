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
