from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
from typing import Callable, Mapping

import httpx

from app.repositories.devices import (
    DeviceAlreadyExistsError,
    DeviceAuthRecord,
    DeviceCreator,
)
from app.security.credentials import hash_secret


@dataclass(frozen=True)
class ProvisionedDevice:
    device_id: str
    device_secret: str


MOBILE_ENV_KEYS = (
    "ALERTAM_API_BASE_URL",
    "ALERTAM_DEVICE_ID",
    "ALERTAM_DEVICE_SECRET",
)
MOBILE_ENV_COMMENT = "# Provisionamento mobile AlertaM"


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


def _parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def load_admin_credentials(
    env_path: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    file_values = (
        _parse_env_text(env_path.read_text(encoding="utf-8"))
        if env_path.is_file()
        else {}
    )
    runtime = os.environ if environ is None else environ

    def resolve(name: str) -> str:
        value = runtime.get(name)
        if value is None or not str(value).strip():
            value = file_values.get(name, "")
        return str(value).strip().strip('"').strip("'")

    placeholder = "[SENSITIVE]"
    supabase_url = resolve("SUPABASE_URL")
    current_key = resolve("SUPABASE_SECRET_KEY")
    legacy_key = resolve("SUPABASE_SERVICE_ROLE_KEY")
    server_key = (
        current_key
        if current_key and current_key != placeholder
        else legacy_key
        if legacy_key and legacy_key != placeholder
        else ""
    )

    if supabase_url == placeholder:
        raise ValueError(
            "SUPABASE_URL contém o placeholder [SENSITIVE] da Vercel. "
            f"Preencha um valor local válido em {env_path}."
        )

    missing: list[str] = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not server_key:
        if current_key == placeholder or legacy_key == placeholder:
            raise ValueError(
                "SUPABASE_SECRET_KEY contém o placeholder [SENSITIVE] da Vercel. "
                f"Preencha uma chave administrativa local válida em {env_path}."
            )
        missing.append("SUPABASE_SECRET_KEY")
    if missing:
        raise ValueError(
            "credenciais administrativas ausentes: "
            + ", ".join(missing)
            + f". Configure {env_path} ou o ambiente."
        )
    return supabase_url, server_key


def _admin_headers(server_key: str) -> dict[str, str]:
    headers = {
        "apikey": server_key,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if not server_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {server_key}"
    return headers


def _raise_for_supabase_admin(response) -> None:
    status_code = getattr(response, "status_code", None)
    if status_code in {401, 403}:
        raise ValueError(
            "Supabase recusou as credenciais administrativas "
            f"(HTTP {status_code}). Verifique SUPABASE_URL e "
            "SUPABASE_SECRET_KEY/SUPABASE_SERVICE_ROLE_KEY."
        )
    response.raise_for_status()


def sync_device_secret(
    client,
    supabase_url: str,
    server_key: str,
    device_id: str,
    device_secret_hash: str,
    *,
    allow_update: bool = True,
    accept_matching: bool = False,
) -> str:
    base_url = supabase_url.rstrip("/")
    headers = _admin_headers(server_key)
    params = {
        "select": "device_id,device_secret_hash",
        "device_id": f"eq.{device_id}",
        "limit": "1",
    }
    response = client.get(
        f"{base_url}/rest/v1/devices",
        headers=headers,
        params=params,
    )
    _raise_for_supabase_admin(response)
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("resposta inválida ao consultar dispositivo")

    if rows:
        row = rows[0]
        if not isinstance(row, dict):
            raise ValueError("resposta inválida ao consultar dispositivo")
        current_hash = str(row.get("device_secret_hash", ""))
        if not allow_update:
            if accept_matching and current_hash == device_secret_hash:
                return "unchanged"
            raise DeviceAlreadyExistsError(
                f"{device_id}: device_id já existe com outro segredo; "
                "não copie o .env entre computadores"
            )
        if current_hash == device_secret_hash:
            return "unchanged"
        response = client.patch(
            f"{base_url}/rest/v1/devices",
            headers=headers,
            params={"device_id": f"eq.{device_id}"},
            json={
                "device_secret_hash": device_secret_hash,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        _raise_for_supabase_admin(response)
        return "updated"

    response = client.post(
        f"{base_url}/rest/v1/devices",
        headers=headers,
        json={
            "device_id": device_id,
            "device_secret_hash": device_secret_hash,
        },
    )
    _raise_for_supabase_admin(response)
    return "created"


def render_mobile_env(
    existing: str,
    *,
    api_base_url: str,
    device_id: str,
    device_secret: str,
) -> str:
    kept: list[str] = []
    for line in existing.splitlines():
        stripped = line.lstrip()
        if stripped == MOBILE_ENV_COMMENT:
            continue
        if any(stripped.startswith(f"{key}=") for key in MOBILE_ENV_KEYS):
            continue
        kept.append(line)

    while kept and not kept[-1].strip():
        kept.pop()
    if kept:
        kept.append("")
    kept.extend(
        [
            MOBILE_ENV_COMMENT,
            f"ALERTAM_API_BASE_URL={api_base_url}",
            f"ALERTAM_DEVICE_ID={device_id}",
            f"ALERTAM_DEVICE_SECRET={device_secret}",
        ]
    )
    return "\n".join(kept) + "\n"


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    if os.name != "nt":
        temp_path.chmod(0o600)
    os.replace(temp_path, path)


def _existing_mobile_identity(env_path: Path) -> tuple[str, str] | None:
    if not env_path.is_file():
        return None
    values = _parse_env_text(env_path.read_text(encoding="utf-8"))
    present = {key: values.get(key, "").strip() for key in MOBILE_ENV_KEYS}
    count = sum(bool(value) for value in present.values())
    if count == 0:
        return None
    if count != len(MOBILE_ENV_KEYS):
        missing = [key for key, value in present.items() if not value]
        raise ValueError(
            "configuração mobile parcial no .env do Desktop; faltando: "
            + ", ".join(missing)
        )
    return present["ALERTAM_DEVICE_ID"], present["ALERTAM_DEVICE_SECRET"]


def _generate_device_id(
    prefix: str,
    *,
    token_factory: Callable[[int], str] = secrets.token_hex,
) -> str:
    clean_prefix = prefix.strip().lower().strip("-")
    if not clean_prefix:
        raise ValueError("device prefix vazio")
    return f"{clean_prefix}-{token_factory(4).lower()}"


def _apply_provisioning(
    *,
    desktop_env: Path,
    admin_env: Path,
    api_base_url: str,
    explicit_device_id: str | None,
    device_prefix: str,
    secret_factory: Callable[[int], str],
    token_factory: Callable[[int], str],
    client,
) -> tuple[str, str]:
    existing = _existing_mobile_identity(desktop_env)
    generated_new_identity = existing is None and explicit_device_id is None

    if existing is not None:
        existing_device_id, device_secret = existing
        if explicit_device_id and explicit_device_id != existing_device_id:
            raise ValueError(
                "o .env já pertence a outro device_id; "
                "não altere a identidade deste Desktop silenciosamente"
            )
        device_id = existing_device_id
    else:
        device_id = explicit_device_id or _generate_device_id(
            device_prefix,
            token_factory=token_factory,
        )
        device_secret = secret_factory(32)

    supabase_url, server_key = load_admin_credentials(admin_env)

    if generated_new_identity:
        for _ in range(5):
            try:
                action = sync_device_secret(
                    client,
                    supabase_url,
                    server_key,
                    device_id,
                    hash_secret(device_secret),
                    allow_update=False,
                )
                break
            except DeviceAlreadyExistsError:
                device_id = _generate_device_id(
                    device_prefix,
                    token_factory=token_factory,
                )
        else:
            raise RuntimeError(
                "não foi possível gerar um device_id único após 5 tentativas"
            )
    elif existing is not None:
        action = sync_device_secret(
            client,
            supabase_url,
            server_key,
            device_id,
            hash_secret(device_secret),
            allow_update=False,
            accept_matching=True,
        )
    else:
        action = sync_device_secret(
            client,
            supabase_url,
            server_key,
            device_id,
            hash_secret(device_secret),
            allow_update=True,
        )

    current_text = (
        desktop_env.read_text(encoding="utf-8")
        if desktop_env.is_file()
        else ""
    )
    _write_text_atomic(
        desktop_env,
        render_mobile_env(
            current_text,
            api_base_url=api_base_url,
            device_id=device_id,
            device_secret=device_secret,
        ),
    )
    return device_id, action


def main(
    argv: list[str] | None = None,
    *,
    secret_factory: Callable[[int], str] = secrets.token_urlsafe,
    token_factory: Callable[[int], str] = secrets.token_hex,
    client_factory: Callable[..., object] = httpx.Client,
) -> int:
    parser = argparse.ArgumentParser(
        description="Gera ou aplica credencial de dispositivo AlertaM.",
    )
    parser.add_argument("device_id", nargs="?")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Registra/atualiza o device no Supabase e grava o .env do Desktop.",
    )
    parser.add_argument("--desktop-env", type=Path)
    parser.add_argument("--admin-env", type=Path)
    parser.add_argument("--api-base-url")
    parser.add_argument("--device-prefix", default="pecem")
    args = parser.parse_args(argv)

    if not args.apply:
        device_id = args.device_id or _generate_device_id(
            args.device_prefix,
            token_factory=token_factory,
        )
        device_secret = secret_factory(32)
        print(f"DEVICE_ID={device_id}")
        print(f"DEVICE_SECRET={device_secret}")
        print()
        print("-- Execute uma única vez no SQL Editor do Supabase:")
        print(render_insert_sql(device_id, device_secret))
        return 0

    if args.desktop_env is None:
        parser.error("--desktop-env é obrigatório com --apply")
    if not args.api_base_url:
        parser.error("--api-base-url é obrigatório com --apply")

    admin_env = args.admin_env or (
        Path(__file__).resolve().parents[1] / ".env.prod"
    )

    try:
        with client_factory(timeout=10.0) as client:
            device_id, action = _apply_provisioning(
                desktop_env=args.desktop_env.resolve(),
                admin_env=admin_env.resolve(),
                api_base_url=args.api_base_url.rstrip("/"),
                explicit_device_id=args.device_id,
                device_prefix=args.device_prefix,
                secret_factory=secret_factory,
                token_factory=token_factory,
                client=client,
            )
    except (
        DeviceAlreadyExistsError,
        OSError,
        ValueError,
        RuntimeError,
        httpx.HTTPError,
    ) as exc:
        parser.exit(2, f"Erro de provisionamento: {exc}\n")

    print(f"DEVICE_ID={device_id}")
    print(f"Banco: {'criado' if action == 'created' else 'sincronizado'}")
    print(f"Desktop .env atualizado: {args.desktop_env.resolve()}")
    print("DEVICE_SECRET gerado/sincronizado sem ser exibido no console.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
