create or replace function public.cleanup_event_retention(
    p_now timestamptz default clock_timestamp()
)
returns table (
    deleted_deliveries bigint,
    deleted_events bigint
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_cutoff timestamptz := p_now - interval '30 days';
    v_deleted_deliveries bigint := 0;
    v_deleted_events bigint := 0;
begin
    delete from public.push_deliveries pd
    using public.maneuver_events me
    where
        pd.event_id = me.event_id
        and me.ingested_at < v_cutoff;

    get diagnostics v_deleted_deliveries = row_count;
    delete from public.maneuver_events me
    where me.ingested_at < v_cutoff;

    get diagnostics v_deleted_events = row_count;

    return query
    select v_deleted_deliveries, v_deleted_events;
end;
$$;

revoke all on function public.cleanup_event_retention(timestamptz)
    from public, anon, authenticated;

grant execute on function public.cleanup_event_retention(timestamptz)
    to service_role;

-- Deploy gate:
-- Schedule select public.cleanup_event_retention(); with Supabase Cron
-- only after migrations 004-006 are applied and verified in the target project.
