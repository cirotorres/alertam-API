from pathlib import Path

MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "012_vessel_tracking_deliveries.sql"
)


def test_tracking_deliveries_have_separate_table_and_required_statuses():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists public.vessel_tracking_deliveries" in sql
    assert "references public.vessel_tracking_events(event_id)" in sql
    assert "references public.push_installations(installation_id)" in sql
    for status in (
        "sending",
        "delivered",
        "ignored_foreground",
        "ignored_before_tracking",
        "retry_pending",
        "permanent_failure",
    ):
        assert f"'{status}'" in sql


def test_tracking_delivery_claim_requires_active_push_installation():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "claim_vessel_tracking_delivery" in sql
    assert "pi.active = true" in sql
    assert "retry_pending" in sql
    assert "make_interval" in sql
