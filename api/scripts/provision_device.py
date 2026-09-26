from __future__ import annotations

import argparse
from dataclasses import dataclass
import secrets
from typing import Callable

from app.repositories.devices import DeviceAuthRecord, DeviceCreator
from app.security.credentials import hash_secret


@dataclass(frozen=True)
class ProvisionedDevice:
    device_id: str
    device_secret: str


def provision_device(
    repository: DeviceCreator,
    device_id: str,
    *,
    secret_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> ProvisionedDevice:
    secret = secret_factory(32)
    repository.create_device(
        DeviceAuthRecord(
            device_id=device_id,
            device_secret_hash=hash_secret(secret),
            view_secret_hash=None,
        )
    )
    return ProvisionedDevice(
        device_id=device_id,
        device_secret=secret,
    )


def render_insert_sql(device_id: str, device_secret: str) -> str:
    safe_device_id = device_id.replace("'", "''")
    secret_hash = hash_secret(device_secret)
    return (
        "insert into public.devices "
        "(device_id, device_secret_hash, view_secret_hash, snapshot) "
        f"values ('{safe_device_id}', '{secret_hash}', null, null);"
    )


def main(
    argv: list[str] | None = None,
    *,
    secret_factory: Callable[[int], str] = secrets.token_urlsafe,
) -> int:
    parser = argparse.ArgumentParser(
        description="Gera credencial inicial para um dispositivo AlertaM.",
    )
    parser.add_argument("device_id")
    args = parser.parse_args(argv)

    device_secret = secret_factory(32)
    print(f"DEVICE_ID={args.device_id}")
    print(f"DEVICE_SECRET={device_secret}")
    print()
    print("-- Execute uma única vez no SQL Editor do Supabase:")
    print(render_insert_sql(args.device_id, device_secret))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
