from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "016_mobile_pairing_codes.sql"
)


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_pairing_codes_are_short_lived_single_redeem_credentials():
    text = sql()

    assert "mobile_pairing_codes" in text
    assert "redeemed_at" in text
    assert "ticket_hash" in text
    assert "consumed_for" in text
    assert "redeem_mobile_pairing_code" in text
    assert "consume_mobile_pairing_ticket" in text


def test_pairing_code_redeem_has_global_failure_window():
    text = sql()

    assert "mobile_pairing_redeem_windows" in text
    assert ">= 30" in text
    assert "rate_limited" in text


def test_view_secret_rotation_invalidates_pending_pairing_code():
    text = sql()

    assert "create or replace function public.rotate_device_view_secret" in text
    assert "delete from public.mobile_pairing_codes" in text
    assert "where device_id = p_device_id" in text
