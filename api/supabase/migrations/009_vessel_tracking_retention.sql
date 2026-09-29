create or replace function public.cleanup_vessel_tracking_retention(
    p_now timestamptz default clock_timestamp()
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
    v_cutoff timestamptz := p_now - interval '30 days';
    v_deleted_events bigint := 0;
begin
    delete from public.vessel_tracking_events
    where ingested_at < v_cutoff;

    get diagnostics v_deleted_events = row_count;
    return v_deleted_events;
end;
$$;

revoke all on function public.cleanup_vessel_tracking_retention(timestamptz)
    from public, anon, authenticated;

grant execute on function public.cleanup_vessel_tracking_retention(timestamptz)
    to service_role;

-- Deploy gate:
-- Schedule select public.cleanup_vessel_tracking_retention();
-- only after migrations 008-009 are applied and verified.
