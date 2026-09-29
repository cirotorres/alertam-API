create table if not exists public.vessel_tracking_events (
    ingestion_id bigint generated always as identity primary key,
    event_id uuid not null unique,
    device_id text not null references public.devices(device_id) on delete cascade,
    vessel_identity text not null,
    vessel_imo text null,
    vessel_name text not null,
    occurred_at timestamptz not null,
    event_payload jsonb not null,
    ingested_at timestamptz not null default clock_timestamp()
);

create index if not exists vessel_tracking_events_device_ingestion_idx
    on public.vessel_tracking_events (device_id, ingestion_id desc);

create index if not exists vessel_tracking_events_device_identity_ingestion_idx
    on public.vessel_tracking_events (
        device_id,
        vessel_identity,
        ingestion_id desc
    );

create index if not exists vessel_tracking_events_device_occurred_idx
    on public.vessel_tracking_events (device_id, occurred_at desc);

alter table public.vessel_tracking_events enable row level security;

revoke all on table public.vessel_tracking_events from anon, authenticated;

create or replace function public.accept_vessel_tracking_event(
    p_device_id text,
    p_event jsonb
)
returns table (
    status text,
    ingestion_id bigint,
    ingested_at timestamptz,
    event_payload jsonb
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_event_id uuid;
    v_ingestion_id bigint;
    v_ingested_at timestamptz;
    v_payload jsonb;
    v_device_id text;
begin
    if not exists (
        select 1 from public.devices d where d.device_id = p_device_id
    ) then
        return query
        select
            'device_not_found'::text,
            null::bigint,
            null::timestamptz,
            null::jsonb;
        return;
    end if;

    v_event_id := (p_event->>'event_id')::uuid;

    insert into public.vessel_tracking_events (
        event_id,
        device_id,
        vessel_identity,
        vessel_imo,
        vessel_name,
        occurred_at,
        event_payload
    )
    values (
        v_event_id,
        p_device_id,
        p_event->>'vessel_identity',
        nullif(p_event->>'vessel_imo', ''),
        p_event->>'vessel_name',
        (p_event->>'occurred_at')::timestamptz,
        p_event
    )
    on conflict (event_id) do nothing
    returning
        public.vessel_tracking_events.ingestion_id,
        public.vessel_tracking_events.ingested_at,
        public.vessel_tracking_events.event_payload
    into v_ingestion_id, v_ingested_at, v_payload;

    if found then
        return query
        select 'accepted'::text, v_ingestion_id, v_ingested_at, v_payload;
        return;
    end if;

    select
        vte.ingestion_id,
        vte.ingested_at,
        vte.event_payload,
        vte.device_id
    into
        v_ingestion_id,
        v_ingested_at,
        v_payload,
        v_device_id
    from public.vessel_tracking_events vte
    where vte.event_id = v_event_id;

    return query
    select
        case
            when v_device_id = p_device_id and v_payload = p_event
                then 'idempotent'::text
            else 'payload_mismatch'::text
        end,
        v_ingestion_id,
        v_ingested_at,
        v_payload;
end;
$$;

revoke all on function public.accept_vessel_tracking_event(text, jsonb)
    from public, anon, authenticated;

grant execute on function public.accept_vessel_tracking_event(text, jsonb)
    to service_role;
