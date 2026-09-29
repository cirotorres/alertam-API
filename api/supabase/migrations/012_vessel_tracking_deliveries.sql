create table if not exists public.vessel_tracking_deliveries (
    event_id uuid not null
        references public.vessel_tracking_events(event_id) on delete cascade,
    installation_id uuid not null
        references public.push_installations(installation_id) on delete cascade,
    status text not null,
    claimed_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    primary key (event_id, installation_id),
    constraint vessel_tracking_deliveries_status check (
        status in (
            'SENDING',
            'DELIVERED',
            'IGNORED_FOREGROUND',
            'IGNORED_BEFORE_TRACKING',
            'RETRY_PENDING',
            'PERMANENT_FAILURE'
        )
    )
);

create index if not exists vessel_tracking_deliveries_updated_idx
    on public.vessel_tracking_deliveries (updated_at);

alter table public.vessel_tracking_deliveries enable row level security;
revoke all on table public.vessel_tracking_deliveries
    from anon, authenticated;

create or replace function public.claim_vessel_tracking_delivery(
    p_event_id uuid,
    p_installation_id uuid,
    p_lease_seconds integer
)
returns table (claimed boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_claimed boolean := false;
begin
    if not exists (
        select 1
        from public.vessel_tracking_events vte
        where vte.event_id = p_event_id
    ) or not exists (
        select 1
        from public.push_installations pi
        where pi.installation_id = p_installation_id
          and pi.active = true
    ) then
        return query select false;
        return;
    end if;

    insert into public.vessel_tracking_deliveries (
        event_id,
        installation_id,
        status,
        claimed_at,
        updated_at
    )
    values (
        p_event_id,
        p_installation_id,
        'SENDING',
        v_now,
        v_now
    )
    on conflict (event_id, installation_id) do update
    set
        status = 'SENDING',
        claimed_at = v_now,
        updated_at = v_now
    where
        public.vessel_tracking_deliveries.status = 'RETRY_PENDING'
        or (
            public.vessel_tracking_deliveries.status = 'SENDING'
            and public.vessel_tracking_deliveries.claimed_at
                <= v_now - make_interval(secs => p_lease_seconds)
        )
    returning true into v_claimed;

    return query select coalesce(v_claimed, false);
end;
$$;

create or replace function public.set_vessel_tracking_delivery_status(
    p_event_id uuid,
    p_installation_id uuid,
    p_status text
)
returns table (updated boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer;
    v_now timestamptz := clock_timestamp();
begin
    insert into public.vessel_tracking_deliveries (
        event_id,
        installation_id,
        status,
        claimed_at,
        updated_at
    )
    select
        p_event_id,
        p_installation_id,
        p_status,
        v_now,
        v_now
    where exists (
        select 1
        from public.vessel_tracking_events vte
        where vte.event_id = p_event_id
    ) and exists (
        select 1
        from public.push_installations pi
        where pi.installation_id = p_installation_id
    )
    on conflict (event_id, installation_id) do update
    set
        status = p_status,
        updated_at = v_now;

    get diagnostics v_count = row_count;
    return query select v_count = 1;
end;
$$;

revoke all on function public.claim_vessel_tracking_delivery(
    uuid, uuid, integer
) from public, anon, authenticated;
revoke all on function public.set_vessel_tracking_delivery_status(
    uuid, uuid, text
) from public, anon, authenticated;

grant execute on function public.claim_vessel_tracking_delivery(
    uuid, uuid, integer
) to service_role;
grant execute on function public.set_vessel_tracking_delivery_status(
    uuid, uuid, text
) to service_role;
