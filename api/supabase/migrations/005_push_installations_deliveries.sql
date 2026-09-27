create table if not exists public.push_installations (
    installation_id uuid primary key,
    device_id text not null references public.devices(device_id) on delete cascade,
    endpoint text null,
    p256dh text null,
    auth text null,
    pref_confirmed boolean not null default true,
    pref_updated boolean not null default true,
    pref_completed boolean not null default true,
    pref_cancelled boolean not null default true,
    push_enabled_at timestamptz not null default clock_timestamp(),
    last_seen_at timestamptz not null default clock_timestamp(),
    last_foreground_at timestamptz null,
    active boolean not null default true,
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp()
);

create index if not exists push_installations_device_active_idx
    on public.push_installations (device_id, active);

create table if not exists public.push_deliveries (
    event_id uuid not null references public.maneuver_events(event_id) on delete cascade,
    installation_id uuid not null references public.push_installations(installation_id) on delete cascade,
    status text not null,
    claimed_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    primary key (event_id, installation_id),
    constraint push_deliveries_status check (
        status in (
            'SENDING',
            'DELIVERED',
            'IGNORED_PREFERENCE',
            'IGNORED_FOREGROUND',
            'IGNORED_BEFORE_OPT_IN',
            'RETRY_PENDING',
            'PERMANENT_FAILURE'
        )
    )
);

create index if not exists push_deliveries_updated_idx
    on public.push_deliveries (updated_at);

alter table public.push_installations enable row level security;
alter table public.push_deliveries enable row level security;

revoke all on table public.push_installations from anon, authenticated;
revoke all on table public.push_deliveries from anon, authenticated;

create or replace function public.upsert_push_installation(
    p_device_id text,
    p_installation_id uuid,
    p_endpoint text,
    p_p256dh text,
    p_auth text
)
returns setof public.push_installations
language plpgsql
security definer
set search_path = public
as $$
declare
    v_existing public.push_installations%rowtype;
    v_now timestamptz := clock_timestamp();
begin
    if not exists (
        select 1 from public.devices d where d.device_id = p_device_id
    ) then
        return;
    end if;

    select *
    into v_existing
    from public.push_installations pi
    where pi.installation_id = p_installation_id
    for update;

    if found and v_existing.device_id <> p_device_id then
        return;
    end if;

    if not found then
        insert into public.push_installations (
            installation_id,
            device_id,
            endpoint,
            p256dh,
            auth,
            push_enabled_at,
            last_seen_at,
            active,
            created_at,
            updated_at
        )
        values (
            p_installation_id,
            p_device_id,
            p_endpoint,
            p_p256dh,
            p_auth,
            v_now,
            v_now,
            true,
            v_now,
            v_now
        );
    else
        update public.push_installations
        set
            endpoint = p_endpoint,
            p256dh = p_p256dh,
            auth = p_auth,
            push_enabled_at = case
                when v_existing.active then v_existing.push_enabled_at
                else v_now
            end,
            last_seen_at = v_now,
            active = true,
            updated_at = v_now
        where installation_id = p_installation_id;
    end if;

    return query
    select *
    from public.push_installations pi
    where pi.installation_id = p_installation_id;
end;
$$;

create or replace function public.update_push_preferences(
    p_device_id text,
    p_installation_id uuid,
    p_confirmed boolean,
    p_updated boolean,
    p_completed boolean,
    p_cancelled boolean
)
returns setof public.push_installations
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.push_installations
    set
        pref_confirmed = p_confirmed,
        pref_updated = p_updated,
        pref_completed = p_completed,
        pref_cancelled = p_cancelled,
        last_seen_at = clock_timestamp(),
        updated_at = clock_timestamp()
    where
        installation_id = p_installation_id
        and device_id = p_device_id;

    return query
    select *
    from public.push_installations pi
    where
        pi.installation_id = p_installation_id
        and pi.device_id = p_device_id;
end;
$$;

create or replace function public.touch_push_foreground(
    p_device_id text,
    p_installation_id uuid
)
returns setof public.push_installations
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := clock_timestamp();
begin
    update public.push_installations
    set
        last_seen_at = v_now,
        last_foreground_at = v_now,
        updated_at = v_now
    where
        installation_id = p_installation_id
        and device_id = p_device_id
        and active = true;

    return query
    select *
    from public.push_installations pi
    where
        pi.installation_id = p_installation_id
        and pi.device_id = p_device_id
        and pi.active = true;
end;
$$;

create or replace function public.deactivate_push_installation(
    p_device_id text,
    p_installation_id uuid
)
returns table (updated boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer;
begin
    update public.push_installations
    set
        endpoint = null,
        p256dh = null,
        auth = null,
        active = false,
        last_seen_at = clock_timestamp(),
        updated_at = clock_timestamp()
    where
        installation_id = p_installation_id
        and device_id = p_device_id;

    get diagnostics v_count = row_count;
    return query select v_count = 1;
end;
$$;

create or replace function public.claim_push_delivery(
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
        select 1 from public.maneuver_events me
        where me.event_id = p_event_id
    ) or not exists (
        select 1 from public.push_installations pi
        where pi.installation_id = p_installation_id and pi.active = true
    ) then
        return query select false;
        return;
    end if;

    insert into public.push_deliveries (
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
        public.push_deliveries.status = 'RETRY_PENDING'
        or (
            public.push_deliveries.status = 'SENDING'
            and public.push_deliveries.claimed_at
                <= v_now - make_interval(secs => p_lease_seconds)
        )
    returning true into v_claimed;

    return query select coalesce(v_claimed, false);
end;
$$;

create or replace function public.set_push_delivery_status(
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
    insert into public.push_deliveries (
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
        select 1 from public.maneuver_events me
        where me.event_id = p_event_id
    ) and exists (
        select 1 from public.push_installations pi
        where pi.installation_id = p_installation_id
    )
    on conflict (event_id, installation_id) do update
    set status = p_status, updated_at = v_now;

    get diagnostics v_count = row_count;
    return query select v_count = 1;
end;
$$;

create or replace function public.rotate_device_view_secret(
    p_device_id text,
    p_view_secret_hash text
)
returns table (updated boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_count integer;
begin
    update public.devices
    set
        view_secret_hash = p_view_secret_hash,
        view_secret_updated_at = v_now,
        updated_at = v_now
    where device_id = p_device_id;

    get diagnostics v_count = row_count;

    if v_count = 1 then
        update public.push_installations
        set
            endpoint = null,
            p256dh = null,
            auth = null,
            active = false,
            last_seen_at = v_now,
            updated_at = v_now
        where device_id = p_device_id;
    end if;

    return query select v_count = 1;
end;
$$;

revoke all on function public.upsert_push_installation(text, uuid, text, text, text)
    from public, anon, authenticated;
revoke all on function public.update_push_preferences(text, uuid, boolean, boolean, boolean, boolean)
    from public, anon, authenticated;
revoke all on function public.touch_push_foreground(text, uuid)
    from public, anon, authenticated;
revoke all on function public.deactivate_push_installation(text, uuid)
    from public, anon, authenticated;
revoke all on function public.claim_push_delivery(uuid, uuid, integer)
    from public, anon, authenticated;
revoke all on function public.set_push_delivery_status(uuid, uuid, text)
    from public, anon, authenticated;
revoke all on function public.rotate_device_view_secret(text, text)
    from public, anon, authenticated;

grant execute on function public.upsert_push_installation(text, uuid, text, text, text)
    to service_role;
grant execute on function public.update_push_preferences(text, uuid, boolean, boolean, boolean, boolean)
    to service_role;
grant execute on function public.touch_push_foreground(text, uuid)
    to service_role;
grant execute on function public.deactivate_push_installation(text, uuid)
    to service_role;
grant execute on function public.claim_push_delivery(uuid, uuid, integer)
    to service_role;
grant execute on function public.set_push_delivery_status(uuid, uuid, text)
    to service_role;
grant execute on function public.rotate_device_view_secret(text, text)
    to service_role;
