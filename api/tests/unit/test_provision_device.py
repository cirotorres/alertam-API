from __future__ import annotations

import pytest

from app.repositories.devices import DeviceAlreadyExistsError
from app.repositories.memory import MemoryDeviceRepository
from app.security.credentials import hash_secret
from scripts.provision_device import main, provision_device, render_insert_sql


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
