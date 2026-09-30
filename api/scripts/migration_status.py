from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable, Iterable

import psycopg


@dataclass(frozen=True)
class MigrationStatus:
    local: tuple[str, ...]
    applied: tuple[str, ...]
    pending: tuple[str, ...]
    unknown: tuple[str, ...]
    migration_table_exists: bool = True

    @property
    def is_synced(self) -> bool:
        return (
            self.migration_table_exists
            and not self.pending
            and not self.unknown
        )


def list_local_migrations(migrations_dir: Path) -> tuple[str, ...]:
    if not migrations_dir.is_dir():
        raise ValueError(
            f"diretório de migrations não encontrado: {migrations_dir}"
        )
    return tuple(
        sorted(path.name for path in migrations_dir.glob("*.sql") if path.is_file())
    )


def build_status(
    local: Iterable[str],
    applied: Iterable[str],
    *,
    migration_table_exists: bool = True,
) -> MigrationStatus:
    local_versions = tuple(sorted(set(local)))
    applied_versions = tuple(sorted(set(applied)))
    local_set = set(local_versions)
    applied_set = set(applied_versions)
    return MigrationStatus(
        local=local_versions,
        applied=applied_versions,
        pending=tuple(sorted(local_set - applied_set)),
        unknown=tuple(sorted(applied_set - local_set)),
        migration_table_exists=migration_table_exists,
    )


def fetch_applied_migrations(
    database_url: str,
    *,
    connect: Callable[..., object] = psycopg.connect,
) -> tuple[tuple[str, ...], bool]:
    if not database_url.strip():
        raise ValueError("DATABASE_URL é obrigatório")

    with connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "select to_regclass('public.schema_migrations') is not null"
            )
            row = cursor.fetchone()
            table_exists = bool(row and row[0])
            if not table_exists:
                return (), False

            cursor.execute(
                "select version from public.schema_migrations order by version"
            )
            return tuple(str(row[0]) for row in cursor.fetchall()), True


def render_status(
    status: MigrationStatus,
    *,
    database_label: str = "Supabase / produção",
) -> str:
    lines = [
        f"Banco: {database_label}",
        "",
        f"Migrations locais:    {len(status.local)}",
        f"Migrations aplicadas: {len(status.applied)}",
        f"Pendentes:            {len(status.pending)}",
        f"Desconhecidas:        {len(status.unknown)}",
    ]

    if not status.migration_table_exists:
        lines.extend(
            [
                "",
                "AVISO: public.schema_migrations ainda não existe no banco.",
            ]
        )

    if status.pending:
        lines.extend(["", "PENDENTES:"])
        lines.extend(f"  {version}" for version in status.pending)

    if status.unknown:
        lines.extend(["", "DESCONHECIDAS NO BANCO:"])
        lines.extend(f"  {version}" for version in status.unknown)

    if status.is_synced:
        lines.extend(["", "✓ Banco atualizado"])
    else:
        lines.extend(["", "⚠ Banco/repositório não estão sincronizados"])
        if status.pending:
            lines.extend(
                [
                    "Para aplicar somente as pendentes:",
                    "  make prod-migrate",
                ]
            )
        if status.unknown:
            lines.extend(
                [
                    "Investigue as migrations desconhecidas antes de alterar o banco.",
                    "Elas estão registradas no banco, mas não existem neste checkout.",
                ]
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compara migrations SQL locais com public.schema_migrations "
            "sem modificar o banco."
        )
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path("supabase/migrations"),
    )
    parser.add_argument(
        "--database-label",
        default="Supabase / produção",
    )
    args = parser.parse_args(argv)

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        parser.exit(2, "Erro: DATABASE_URL é obrigatório.\n")

    try:
        local = list_local_migrations(args.migrations_dir)
        applied, table_exists = fetch_applied_migrations(database_url)
    except (OSError, ValueError, psycopg.Error) as exc:
        parser.exit(2, f"Erro ao verificar migrations: {exc}\n")

    status = build_status(
        local,
        applied,
        migration_table_exists=table_exists,
    )
    print(render_status(status, database_label=args.database_label))
    return 0 if status.is_synced else 1


if __name__ == "__main__":
    raise SystemExit(main())
