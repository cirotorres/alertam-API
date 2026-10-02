-- Migration 015: schedule automatic 30-day maneuver-event retention.
-- pg_cron uses UTC; 03:15 UTC is 00:15 in Fortaleza (UTC-3).

create extension if not exists pg_cron;

select cron.schedule(
    'alertam-cleanup-event-retention',
    '15 3 * * *',
    $$select public.cleanup_event_retention();$$
);
