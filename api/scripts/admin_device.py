from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import secrets
from typing import Callable, Mapping

import httpx
import psycopg

from app.repositories.devices import DeviceAlreadyExistsError
from app.security.credentials import hash_secret
from scripts.provision_device import (
    MOBILE_ENV_KEYS,
    _admin_headers,
    _generate_device_id,
    _parse_env_text,
    _raise_for_supabase_admin,
    _write_text_atomic,
    load_admin_credentials,
    render_mobile_env,
)


@dataclass(frozen=True)
class PreparedDeviceIdentity:
    api_base_url: str
    device_id: str
    device_secret: str = field(repr=False)


def load_prepared_identity(path: Path) -> PreparedDeviceIdentity:
    if not path.is_file():
        raise ValueError(f"arquivo de identidade não encontrado: {path}")

    values = _parse_env_text(path.read_text(encoding="utf-8"))
    keys = set(values)
    required = set(MOBILE_ENV_KEYS)
    missing = [key for key in MOBILE_ENV_KEYS if not values.get(key, "").strip()]
    if missing:
        raise ValueError(
            "identidade preparada incompleta; faltando: " + ", ".join(missing)
        )
    if keys != required:
        raise ValueError(
            "arquivo de identidade deve conter somente as três chaves mobile"
        )

    return PreparedDeviceIdentity(
        api_base_url=values["ALERTAM_API_BASE_URL"].strip(),
        device_id=values["ALERTAM_DEVICE_ID"].strip(),
        device_secret=values["ALERTAM_DEVICE_SECRET"].strip(),
    )


def prepare_new_identity(
    output_env: Path,
    *,
    api_base_url: str,
    device_prefix: str,
    client,
    supabase_url: str,
    server_key: str,
    secret_factory: Callable[[int], str] = secrets.token_urlsafe,
    token_factory: Callable[[int], str] = secrets.token_hex,
) -> PreparedDeviceIdentity:
    base_url = supabase_url.rstrip("/")
    device_id = ""
    for _attempt in range(5):
        candidate = _generate_device_id(device_prefix, token_factory=token_factory)
        response = client.get(
            f"{base_url}/rest/v1/devices",
            headers=_admin_headers(server_key),
            params={
                "select": "device_id",
                "device_id": f"eq.{candidate}",
                "limit": "1",
            },
        )
        _raise_for_supabase_admin(response)
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("resposta inválida ao consultar dispositivo")
        if not rows:
            device_id = candidate
            break
    if not device_id:
        raise ValueError("não foi possível gerar device_id inédito após 5 tentativas")

    device_secret = secret_factory(32)
    identity = PreparedDeviceIdentity(
        api_base_url=api_base_url,
        device_id=device_id,
        device_secret=device_secret,
    )
    rendered = render_mobile_env(
        "",
        api_base_url=identity.api_base_url,
        device_id=identity.device_id,
        device_secret=identity.device_secret,
    )
    _write_text_atomic(output_env, rendered)
    return identity



def normalize_device_description(value: str) -> str:
    description = str(value).strip()
    if not description or len(description) > 200:
        raise ValueError("description deve conter entre 1 e 200 caracteres")
    return description


def register_prepared_identity(
    identity: PreparedDeviceIdentity,
    *,
    description: str,
    client,
    supabase_url: str,
    server_key: str,
) -> None:
    normalized_description = normalize_device_description(description)
    base_url = supabase_url.rstrip("/")
    headers = _admin_headers(server_key)
    response = client.get(
        f"{base_url}/rest/v1/devices",
        headers=headers,
        params={
            "select": "device_id",
            "device_id": f"eq.{identity.device_id}",
            "limit": "1",
        },
    )
    _raise_for_supabase_admin(response)
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("resposta inválida ao consultar dispositivo")
    if rows:
        raise DeviceAlreadyExistsError(identity.device_id)

    response = client.post(
        f"{base_url}/rest/v1/devices",
        headers=headers,
        json={
            "device_id": identity.device_id,
            "device_secret_hash": hash_secret(identity.device_secret),
            "description": normalized_description,
            "enabled": True,
        },
    )
    if getattr(response, "status_code", None) == 409:
        raise DeviceAlreadyExistsError(identity.device_id)
    _raise_for_supabase_admin(response)



def main(
    argv: list[str] | None = None,
    *,
    secret_factory: Callable[[int], str] = secrets.token_urlsafe,
    token_factory: Callable[[int], str] = secrets.token_hex,
    client_factory: Callable[..., object] = httpx.Client,
    connect_factory: Callable[..., object] = psycopg.connect,
) -> int:
    parser = argparse.ArgumentParser(
        description="Administra identidade temporária de Desktop AlertaM.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--output-env", type=Path, required=True)
    prepare_parser.add_argument("--admin-env", type=Path, required=True)
    prepare_parser.add_argument("--api-base-url", required=True)
    prepare_parser.add_argument("--device-prefix", default="pecem")

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--identity-env", type=Path, required=True)
    register_parser.add_argument("--admin-env", type=Path, required=True)
    register_parser.add_argument("--description", required=True)

    compensate_parser = subparsers.add_parser("compensate")
    compensate_parser.add_argument("--identity-env", type=Path, required=True)
    compensate_parser.add_argument("--admin-env", type=Path, required=True)

    args = parser.parse_args(argv)

    try:
        if args.command == "compensate":
            identity = load_prepared_identity(args.identity_env.resolve())
            database_url = load_admin_database_url(args.admin_env.resolve())
            removed = compensate_prepared_identity(
                identity,
                database_url=database_url,
                connect_factory=connect_factory,
            )
            if not removed:
                parser.exit(
                    2,
                    f"Compensação recusada para DEVICE_ID={identity.device_id}.\n",
                )
            print(f"DEVICE_ID={identity.device_id}")
            print("Device preparado removido com segurança.")
            return 0

        supabase_url, server_key = load_admin_credentials(args.admin_env.resolve())
        with client_factory(timeout=10.0) as client:
            if args.command == "prepare":
                identity = prepare_new_identity(
                    args.output_env.resolve(),
                    api_base_url=args.api_base_url.rstrip("/"),
                    device_prefix=args.device_prefix,
                    client=client,
                    supabase_url=supabase_url,
                    server_key=server_key,
                    secret_factory=secret_factory,
                    token_factory=token_factory,
                )
                print(f"DEVICE_ID={identity.device_id}")
                print(f"Identity env preparado: {args.output_env.resolve()}")
                return 0

            identity = load_prepared_identity(args.identity_env.resolve())
            register_prepared_identity(
                identity,
                description=args.description,
                client=client,
                supabase_url=supabase_url,
                server_key=server_key,
            )
            print(f"DEVICE_ID={identity.device_id}")
            print("Device registrado no backend.")
            return 0
    except psycopg.Error:
        parser.exit(
            2,
            "Erro administrativo: falha segura na compensação via banco.\n",
        )
    except (
        DeviceAlreadyExistsError,
        OSError,
        RuntimeError,
        ValueError,
        httpx.HTTPError,
    ) as exc:
        parser.exit(2, f"Erro administrativo: {exc}\n")


_DEPENDENCY_PROBES = (
    ("maneuver_events", "device_id"),
    ("push_installations", "device_id"),
    ("vessel_tracking_events", "device_id"),
    ("mobile_installations", "device_id"),
    ("tracked_vessels", "device_id"),
    ("webpilot_auth_realm_devices", "device_id"),
    ("cloud_bindings", "device_id"),
    ("webpilot_session_publishers", "device_id"),
    ("mobile_session_switches", "from_device_id"),
    ("mobile_session_switches", "to_device_id"),
)


def load_admin_database_url(
    env_path: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> str:
    file_values = (
        _parse_env_text(env_path.read_text(encoding="utf-8"))
        if env_path.is_file()
        else {}
    )
    runtime = os.environ if environ is None else environ
    raw = runtime.get("SUPABASE_DB_URL")
    if raw is None or not str(raw).strip():
        raw = file_values.get("SUPABASE_DB_URL", "")
    value = str(raw).strip().strip('"').strip("'")
    if not value or value == "[SENSITIVE]" or "<password>" in value:
        raise ValueError(
            f"SUPABASE_DB_URL ausente ou inválida em {env_path}"
        )
    return value


def compensate_prepared_identity(
    identity: PreparedDeviceIdentity,
    *,
    database_url: str,
    connect_factory: Callable[..., object] = psycopg.connect,
) -> bool:
    expected_hash = hash_secret(identity.device_secret)
    with connect_factory(database_url) as connection:
        row = connection.execute(
            """
            select
                device_id,
                device_secret_hash,
                view_secret_hash,
                snapshot,
                boot_id,
                sequence,
                generated_at,
                received_at
            from public.devices
            where device_id = %s
            for update
            """,
            (identity.device_id,),
        ).fetchone()
        if row is None:
            return False

        (
            _device_id,
            stored_hash,
            view_secret_hash,
            snapshot,
            boot_id,
            sequence,
            generated_at,
            received_at,
        ) = row
        if stored_hash != expected_hash:
            return False
        if any(
            value is not None
            for value in (
                view_secret_hash,
                snapshot,
                boot_id,
                sequence,
                generated_at,
                received_at,
            )
        ):
            return False

        for table, column in _DEPENDENCY_PROBES:
            dependent = connection.execute(
                f"select 1 from public.{table} where {column} = %s limit 1",
                (identity.device_id,),
            ).fetchone()
            if dependent is not None:
                return False

        deleted = connection.execute(
            """
            delete from public.devices
            where device_id = %s
              and device_secret_hash = %s
              and view_secret_hash is null
              and snapshot is null
              and boot_id is null
              and sequence is null
              and generated_at is null
              and received_at is null
            returning device_id
            """,
            (identity.device_id, expected_hash),
        ).fetchone()
        return deleted is not None



if __name__ == "__main__":
    raise SystemExit(main())
