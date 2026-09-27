create table if not exists public.maneuver_events (
    ingestion_id bigint generated always as identity primary key,
    event_id uuid not null unique,
    device_id text not null references public.devices(device_id) on delete cascade,
    maneuver_id uuid not null,
    event_type text not null,
    occurred_at timestamptz not null,
    event_payload jsonb not null,
    ingested_at timestamptz not null default clock_timestamp(),
    constraint maneuver_events_event_type
        check (event_type in ('CONFIRMED', 'UPDATED', 'COMPLETED', 'CANCELLED'))
);

create index if not exists maneuver_events_device_ingestion_idx
    on public.maneuver_events (device_id, ingestion_id desc);

create index if not exists maneuver_events_device_occurred_idx
    on public.maneuver_events (device_id, occurred_at desc);

alter table public.maneuver_events enable row level security;

revoke all on table public.maneuver_events from anon, authenticated;

create or replace function public.accept_maneuver_event(
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
    v_maneuver_id uuid;
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
    v_maneuver_id := (p_event->>'maneuver_id')::uuid;

    insert into public.maneuver_events (
        event_id,
        device_id,
        maneuver_id,
        event_type,
        occurred_at,
        event_payload
    )
    values (
        v_event_id,
        p_device_id,
        v_maneuver_id,
        p_event->>'event_type',
        (p_event->>'occurred_at')::timestamptz,
        p_event
    )
    on conflict (event_id) do nothing
    returning
        public.maneuver_events.ingestion_id,
        public.maneuver_events.ingested_at,
        public.maneuver_events.event_payload
    into v_ingestion_id, v_ingested_at, v_payload;

    if found then
        return query
        select 'accepted'::text, v_ingestion_id, v_ingested_at, v_payload;
        return;
    end if;

    select
        me.ingestion_id,
        me.ingested_at,
        me.event_payload,
        me.device_id
    into
        v_ingestion_id,
        v_ingested_at,
        v_payload,
        v_device_id
    from public.maneuver_events me
    where me.event_id = v_event_id;

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

revoke all on function public.accept_maneuver_event(text, jsonb)
    from public, anon, authenticated;

grant execute on function public.accept_maneuver_event(text, jsonb)
    to service_role;
