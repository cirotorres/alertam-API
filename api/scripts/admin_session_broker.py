from __future__ import annotations

import argparse
from pathlib import Path
from uuid import UUID

from app.repositories.session_broker import (
    ProviderScopeProfile,
    RequiredProviderScopeRecord,
    SessionBrokerRepository,
    SessionPublisherRecord,
)
from app.repositories.supabase import SupabaseDeviceRepository
from scripts.provision_device import load_admin_credentials


def _require(value, message: str):
    if value is None:
        raise ValueError(message)
    return value


def configure_required_scope(
    repository: SessionBrokerRepository,
    realm_id: str,
    profile: ProviderScopeProfile,
) -> RequiredProviderScopeRecord:
    return _require(
        repository.set_required_provider_scope(realm_id, profile),
        "realm não encontrado",
    )


def verify_publisher_scope(
    repository: SessionBrokerRepository,
    publisher_id: UUID,
) -> SessionPublisherRecord:
    return _require(
        repository.verify_session_publisher_scope(publisher_id),
        "publisher não encontrado",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Administra provider scope do Session Broker.",
    )
    parser.add_argument("--admin-env", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    required = sub.add_parser("set-required-scope")
    required.add_argument("--realm-id", required=True)
    required.add_argument("--scope-id", required=True)
    required.add_argument("--schema-version", type=int, required=True)
    required.add_argument("--capability", action="append", default=[])

    verify = sub.add_parser("verify-publisher")
    verify.add_argument("--publisher-id", type=UUID, required=True)

    args = parser.parse_args(argv)
    supabase_url, server_key = load_admin_credentials(args.admin_env.resolve())
    repository = SupabaseDeviceRepository(supabase_url, server_key)

    if args.command == "set-required-scope":
        record = configure_required_scope(
            repository,
            args.realm_id,
            ProviderScopeProfile(
                scope_id=args.scope_id,
                schema_version=args.schema_version,
                capabilities=tuple(sorted(args.capability)),
            ),
        )
        print(f"REALM_ID={record.realm_id}")
        print(f"SCOPE_ID={record.profile.scope_id}")
        print(f"SCHEMA_VERSION={record.profile.schema_version}")
        return 0

    publisher = verify_publisher_scope(repository, args.publisher_id)
    print(f"PUBLISHER_ID={publisher.publisher_id}")
    print(f"SCOPE_STATUS={publisher.scope_status.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
