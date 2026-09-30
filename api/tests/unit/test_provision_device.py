from __future__ import annotations

from pathlib import Path

import pytest

from app.repositories.devices import DeviceAlreadyExistsError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from scripts.provision_device import (
    _apply_provisioning,
    load_admin_credentials,
    main,
    provision_device,
    render_insert_sql,
    render_mobile_env,
    sync_device_secret,
)


def test_provision_device_generates_32_byte_secret_and_persists_only_hash():
    requested_sizes: list[int] = []

    def secret_factory(size: int) -> str:
        requested_sizes.append(size)
        return "segredo-gerado-apenas-uma-vez"

    repo = MemoryDeviceRepository()

    provisioned = provision_device(
        repo,
        "pecem-01",
        secret_factory=secret_factory,
    )

    stored = repo.get_device_auth("pecem-01")
    assert requested_sizes == [32]
    assert provisioned.device_id == "pecem-01"
    assert provisioned.device_secret == "segredo-gerado-apenas-uma-vez"

    assert stored.device_secret_hash == hash_secret(provisioned.device_secret)
    assert stored.view_secret_hash is None
    assert provisioned.device_secret not in repr(stored)


def test_provision_device_does_not_silently_overwrite_existing_device():
    repo = MemoryDeviceRepository()

    first = provision_device(
        repo,
        "pecem-01",
        secret_factory=lambda _: "primeiro-segredo",
    )

    with pytest.raises(DeviceAlreadyExistsError):
        provision_device(
            repo,
            "pecem-01",
            secret_factory=lambda _: "segundo-segredo",
        )

    stored = repo.get_device_auth("pecem-01")
    assert stored.device_secret_hash == hash_secret(first.device_secret)
    assert stored.device_secret_hash != hash_secret("segundo-segredo")

def test_render_insert_sql_contains_hash_but_not_plaintext_secret():
    secret = "segredo-nao-deve-ir-para-sql"

    sql = render_insert_sql("pecem-01", secret)

    assert "pecem-01" in sql
    assert hash_secret(secret) in sql
    assert secret not in sql


def test_cli_prints_plaintext_secret_once_and_sql_with_hash(capsys):
    secret = "segredo-mostrado-uma-unica-vez"

    exit_code = main(
        ["pecem-01"],
        secret_factory=lambda size: secret if size == 32 else "",
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.count(secret) == 1
    assert hash_secret(secret) in output
    assert "insert into public.devices" in output.lower()


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSupabaseClient:
    def __init__(self, existing: bool, existing_hash: str | None = None):
        self.existing = existing
        self.existing_hash = existing_hash
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url, *, headers, params):
        self.calls.append(("GET", url, {"headers": headers, "params": params}))
        payload = (
            [{
                "device_id": "pecem-01",
                "device_secret_hash": self.existing_hash or "hash-antigo",
            }]
            if self.existing
            else []
        )
        return FakeResponse(payload)

    def patch(self, url, *, headers, params, json):
        self.calls.append(
            ("PATCH", url, {"headers": headers, "params": params, "json": json})
        )
        return FakeResponse(None, status_code=204)

    def post(self, url, *, headers, json):
        self.calls.append(("POST", url, {"headers": headers, "json": json}))
        return FakeResponse(None, status_code=201)


def test_sync_device_secret_updates_only_hash_for_existing_device():
    client = FakeSupabaseClient(existing=True)

    action = sync_device_secret(
        client,
        "https://project.supabase.co",
        "sb_secret_admin",
        "pecem-01",
        "hash-novo",
    )

    assert action == "updated"
    assert [call[0] for call in client.calls] == ["GET", "PATCH"]
    patch_payload = client.calls[1][2]["json"]
    assert patch_payload["device_secret_hash"] == "hash-novo"
    assert set(patch_payload) == {"device_secret_hash", "updated_at"}
    assert "view_secret_hash" not in patch_payload
    assert "snapshot" not in patch_payload


def test_sync_device_secret_creates_missing_device():
    client = FakeSupabaseClient(existing=False)

    action = sync_device_secret(
        client,
        "https://project.supabase.co",
        "sb_secret_admin",
        "pecem-01",
        "hash-novo",
    )

    assert action == "created"
    assert [call[0] for call in client.calls] == ["GET", "POST"]
    assert client.calls[1][2]["json"] == {
        "device_id": "pecem-01",
        "device_secret_hash": "hash-novo",
    }


def test_render_mobile_env_replaces_mobile_values_and_preserves_unrelated_lines():
    existing = (
        "# config local\n"
        "MODO_DEBUG=true\n"
        "ALERTAM_API_BASE_URL=https://old.example\n"
        "ALERTAM_DEVICE_ID=old-device\n"
        "ALERTAM_DEVICE_SECRET=old-secret\n"
    )

    rendered = render_mobile_env(
        existing,
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-01",
        device_secret="novo-secret",
    )

    assert "# config local" in rendered
    assert "MODO_DEBUG=true" in rendered
    assert "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app" in rendered
    assert "ALERTAM_DEVICE_ID=pecem-01" in rendered
    assert "ALERTAM_DEVICE_SECRET=novo-secret" in rendered
    assert "old-secret" not in rendered


def test_load_admin_credentials_uses_prod_env_without_exposing_unrelated_values(
    tmp_path: Path,
):
    env_file = tmp_path / ".env.prod"
    env_file.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=sb_secret_admin\n"
        "UNRELATED=ignore-me\n",
        encoding="utf-8",
    )

    url, key = load_admin_credentials(env_file, environ={})

    assert url == "https://project.supabase.co"
    assert key == "sb_secret_admin"


def test_load_admin_credentials_rejects_vercel_sensitive_placeholder(tmp_path: Path):
    env_file = tmp_path / ".env.prod"
    env_file.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        'SUPABASE_SECRET_KEY="[SENSITIVE]"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"\[SENSITIVE\]") as exc_info:
        load_admin_credentials(env_file, environ={})

    assert "SUPABASE_SECRET_KEY" in str(exc_info.value)


def test_load_admin_credentials_uses_legacy_key_when_current_key_is_placeholder(
    tmp_path: Path,
):
    env_file = tmp_path / ".env.prod"
    env_file.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=[SENSITIVE]\n"
        "SUPABASE_SERVICE_ROLE_KEY=legacy-service-role\n",
        encoding="utf-8",
    )

    url, key = load_admin_credentials(env_file, environ={})

    assert url == "https://project.supabase.co"
    assert key == "legacy-service-role"


def test_sync_device_secret_explains_supabase_admin_401_without_leaking_key():
    secret = "test-admin-key-should-never-appear"
    client = FakeSupabaseClient(existing=False)
    client.get = lambda *args, **kwargs: FakeResponse(
        {"message": "invalid api key"},
        status_code=401,
    )

    with pytest.raises(ValueError, match="401") as exc_info:
        sync_device_secret(
            client,
            "https://project.supabase.co",
            secret,
            "pecem-01",
            "hash-novo",
        )

    message = str(exc_info.value)
    assert "credenciais administrativas" in message
    assert "SUPABASE_SECRET_KEY" in message
    assert secret not in message


def test_apply_provisioning_generates_independent_device_and_writes_desktop_env(
    tmp_path: Path,
):
    admin_env = tmp_path / ".env.prod"
    admin_env.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=sb_secret_admin\n",
        encoding="utf-8",
    )
    desktop_env = tmp_path / ".env"
    client = FakeSupabaseClient(existing=False)

    device_id, action = _apply_provisioning(
        desktop_env=desktop_env,
        admin_env=admin_env,
        api_base_url="https://alertam-api.vercel.app",
        explicit_device_id=None,
        device_prefix="pecem",
        secret_factory=lambda size: "device-secret" if size == 32 else "",
        token_factory=lambda size: "a1b2c3d4" if size == 4 else "",
        client=client,
    )

    assert device_id == "pecem-a1b2c3d4"
    assert action == "created"
    rendered = desktop_env.read_text(encoding="utf-8")
    assert "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app" in rendered
    assert "ALERTAM_DEVICE_ID=pecem-a1b2c3d4" in rendered
    assert "ALERTAM_DEVICE_SECRET=device-secret" in rendered


def test_apply_provisioning_reuses_existing_desktop_identity(tmp_path: Path):
    admin_env = tmp_path / ".env.prod"
    admin_env.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=sb_secret_admin\n",
        encoding="utf-8",
    )
    desktop_env = tmp_path / ".env"
    desktop_env.write_text(
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-existing\n"
        "ALERTAM_DEVICE_SECRET=existing-secret\n",
        encoding="utf-8",
    )
    client = FakeSupabaseClient(
        existing=True,
        existing_hash=hash_secret("existing-secret"),
    )

    device_id, action = _apply_provisioning(
        desktop_env=desktop_env,
        admin_env=admin_env,
        api_base_url="https://alertam-api.vercel.app",
        explicit_device_id=None,
        device_prefix="pecem",
        secret_factory=lambda _: pytest.fail("nao deveria gerar outro segredo"),
        token_factory=lambda _: pytest.fail("nao deveria gerar outro device_id"),
        client=client,
    )

    assert device_id == "pecem-existing"
    assert action == "unchanged"
    rendered = desktop_env.read_text(encoding="utf-8")
    assert "ALERTAM_DEVICE_ID=pecem-existing" in rendered
    assert "ALERTAM_DEVICE_SECRET=existing-secret" in rendered


def test_apply_provisioning_refuses_existing_device_with_different_secret(
    tmp_path: Path,
):
    admin_env = tmp_path / ".env.prod"
    admin_env.write_text(
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_SECRET_KEY=sb_secret_admin\n",
        encoding="utf-8",
    )
    desktop_env = tmp_path / ".env"
    desktop_env.write_text(
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-copiado\n"
        "ALERTAM_DEVICE_SECRET=segredo-local\n",
        encoding="utf-8",
    )
    client = FakeSupabaseClient(
        existing=True,
        existing_hash=hash_secret("segredo-de-outro-computador"),
    )

    with pytest.raises(DeviceAlreadyExistsError):
        _apply_provisioning(
            desktop_env=desktop_env,
            admin_env=admin_env,
            api_base_url="https://alertam-api.vercel.app",
            explicit_device_id=None,
            device_prefix="pecem",
            secret_factory=lambda _: pytest.fail("nao deve gerar"),
            token_factory=lambda _: pytest.fail("nao deve gerar"),
            client=client,
        )

    assert [call[0] for call in client.calls] == ["GET"]


def test_render_mobile_env_does_not_duplicate_provisioning_comment():
    existing = (
        "# config local\n"
        "# Provisionamento mobile AlertaM\n"
        "ALERTAM_API_BASE_URL=https://alertam-api.vercel.app\n"
        "ALERTAM_DEVICE_ID=pecem-existing\n"
        "ALERTAM_DEVICE_SECRET=existing-secret\n"
    )

    rendered = render_mobile_env(
        existing,
        api_base_url="https://alertam-api.vercel.app",
        device_id="pecem-existing",
        device_secret="existing-secret",
    )

    assert rendered.count("# Provisionamento mobile AlertaM") == 1
