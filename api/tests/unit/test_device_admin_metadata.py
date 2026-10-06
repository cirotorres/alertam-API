from dataclasses import fields
from pathlib import Path

from app.repositories.devices import DeviceAuthRecord


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "018_device_admin_metadata.sql"
)


def test_device_auth_record_has_backward_compatible_admin_metadata_defaults():
    names = {field.name for field in fields(DeviceAuthRecord)}
    assert {"description", "enabled"} <= names

    record = DeviceAuthRecord("pecem-legacy", "hash")
    assert record.description is None
    assert record.enabled is True


def test_migration_018_adds_metadata_without_rewriting_identity_payloads():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "alter table public.devices" in sql
    assert "description text" in sql
    assert "enabled boolean not null default true" in sql
    for forbidden in (
        "update public.devices",
        "device_secret_hash =",
        "view_secret_hash =",
        "snapshot =",
    ):
        assert forbidden not in sql
