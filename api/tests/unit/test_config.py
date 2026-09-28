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


def test_web_push_disabled_does_not_require_vapid_credentials(monkeypatch):
    monkeypatch.delenv("WEB_PUSH_ENABLED", raising=False)
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.web_push_enabled is False
    assert settings.vapid_public_key == ""
    assert settings.vapid_private_key == ""
    assert settings.vapid_subject == ""
    assert settings.push_foreground_fresh_seconds == 75


def test_web_push_enabled_requires_complete_vapid_configuration():
    with pytest.raises(ValueError) as exc_info:
        Settings(
            _env_file=None,
            web_push_enabled=True,
            vapid_public_key="public",
        )

    message = str(exc_info.value)
    assert "VAPID_PRIVATE_KEY" in message
    assert "VAPID_SUBJECT" in message


def test_vapid_private_key_is_hidden_from_settings_repr():
    private_key = "very-secret-vapid-private-key"
    settings = Settings(
        _env_file=None,
        web_push_enabled=True,
        vapid_public_key="public-key",
        vapid_private_key=private_key,
        vapid_subject="mailto:alerts@example.com",
    )

    assert settings.web_push_enabled is True
    assert settings.vapid_private_key == private_key
    assert private_key not in repr(settings)
