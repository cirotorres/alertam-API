from __future__ import annotations

import argparse
from pathlib import Path

from app.repositories.cloud_bindings import (
    CloudBindingsRepository,
    RealmDeviceAuthorizationRecord,
    WebPilotAuthRealmRecord,
)
from app.repositories.supabase import SupabaseDeviceRepository
from scripts.provision_device import load_admin_credentials


def _require(value, message: str):
    if value is None:
        raise ValueError(message)
    return value


def ensure_realm(
    repository: CloudBindingsRepository,
    realm_id: str,
) -> WebPilotAuthRealmRecord:
    return _require(
        repository.ensure_webpilot_auth_realm(realm_id),
        "realm não pôde ser criado",
    )


def activate_realm(
    repository: CloudBindingsRepository,
    realm_id: str,
) -> WebPilotAuthRealmRecord:
    return _require(
        repository.set_webpilot_auth_realm_active(realm_id, True),
        "realm não encontrado",
    )


def deactivate_realm(
    repository: CloudBindingsRepository,
    realm_id: str,
) -> WebPilotAuthRealmRecord:
    return _require(
        repository.set_webpilot_auth_realm_active(realm_id, False),
        "realm não encontrado",
    )


def authorize_device(
    repository: CloudBindingsRepository,
    realm_id: str,
    device_id: str,
) -> RealmDeviceAuthorizationRecord:
    return _require(
        repository.authorize_realm_device(realm_id, device_id),
        "realm/device não encontrado",
    )


def revoke_device(
    repository: CloudBindingsRepository,
    realm_id: str,
    device_id: str,
) -> RealmDeviceAuthorizationRecord:
    return _require(
        repository.revoke_realm_device(realm_id, device_id),
        "autorização não encontrada",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Administra realm WebPilot do AlertaM Cloud.",
    )
    parser.add_argument("--admin-env", type=Path, required=True)
    parser.add_argument("--realm-id", required=True)
    parser.add_argument(
        "command",
        choices=("ensure", "activate", "deactivate", "authorize", "revoke"),
    )
    parser.add_argument("--device-id")
    args = parser.parse_args(argv)

    supabase_url, server_key = load_admin_credentials(args.admin_env.resolve())
    repository = SupabaseDeviceRepository(supabase_url, server_key)

    if args.command == "ensure":
        result = ensure_realm(repository, args.realm_id)
        print(f"REALM_ID={result.realm_id}")
        print(f"ACTIVE={str(result.active).lower()}")
        return 0
    if args.command == "activate":
        result = activate_realm(repository, args.realm_id)
        print(f"REALM_ID={result.realm_id}")
        print("ACTIVE=true")
        return 0
    if args.command == "deactivate":
        result = deactivate_realm(repository, args.realm_id)
        print(f"REALM_ID={result.realm_id}")
        print("ACTIVE=false")
        return 0

    if not args.device_id:
        parser.error("--device-id é obrigatório para authorize/revoke")

    if args.command == "authorize":
        membership = authorize_device(repository, args.realm_id, args.device_id)
        print(f"REALM_ID={membership.realm_id}")
        print(f"DEVICE_ID={membership.device_id}")
        print("AUTHORIZED=true")
        return 0

    membership = revoke_device(repository, args.realm_id, args.device_id)
    print(f"REALM_ID={membership.realm_id}")
    print(f"DEVICE_ID={membership.device_id}")
    print("AUTHORIZED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
