-- Migration 007: optimize device-scoped maneuver timeline lookup

create index if not exists maneuver_events_device_maneuver_ingestion_idx
    on public.maneuver_events (device_id, maneuver_id, ingestion_id);
