create table if not exists public.tracked_vessels (
    tracked_vessel_id uuid primary key default gen_random_uuid(),
    device_id text not null references public.devices(device_id) on delete cascade,
    installation_id uuid not null references public.mobile_installations(installation_id) on delete cascade,
    vessel_identity text not null,
    vessel_imo text null,
    vessel_name text not null,
    started_at timestamptz not null default clock_timestamp(),
    active boolean not null default true,
    stopped_at timestamptz null,
    last_seen_at timestamptz null,
    current jsonb null,
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    unique (installation_id, vessel_identity)
);

create index if not exists tracked_vessels_installation_active_idx
    on public.tracked_vessels (installation_id, active);

create index if not exists tracked_vessels_device_identity_idx
    on public.tracked_vessels (device_id, vessel_identity);

alter table public.tracked_vessels enable row level security;
revoke all on table public.tracked_vessels from anon, authenticated;

create or replace function public.upsert_tracked_vessel(
    p_device_id text,
    p_installation_id uuid,
    p_vessel_identity text,
    p_vessel_imo text,
    p_vessel_name text,
    p_current jsonb,
    p_last_seen_at timestamptz
)
returns setof public.tracked_vessels
language plpgsql
security definer
set search_path = public
as $$
declare
    v_existing public.tracked_vessels%rowtype;
    v_now timestamptz := clock_timestamp();
    v_name text := regexp_replace(
        upper(trim(p_vessel_name)),
        '[[:space:]]+',
        ' ',
        'g'
    );
begin
    if not exists (
        select 1
        from public.mobile_installations mi
        where mi.installation_id = p_installation_id
          and mi.device_id = p_device_id
          and mi.active = true
    ) then
        return;
    end if;

    select *
    into v_existing
    from public.tracked_vessels tv
    where tv.installation_id = p_installation_id
      and tv.vessel_identity = p_vessel_identity
    for update;

    if not found and p_vessel_imo is not null then
        select *
        into v_existing
        from public.tracked_vessels tv
        where tv.installation_id = p_installation_id
          and tv.vessel_imo is null
          and regexp_replace(
                  upper(trim(tv.vessel_name)),
                  '[[:space:]]+',
                  ' ',
                  'g'
              ) = v_name
        order by tv.created_at asc
        limit 1
        for update;
    end if;

    if found then
        update public.tracked_vessels
        set
            vessel_identity = p_vessel_identity,
            vessel_imo = p_vessel_imo,
            vessel_name = p_vessel_name,
            started_at = case when v_existing.active then v_existing.started_at else v_now end,
            active = true,
            stopped_at = null,
            last_seen_at = p_last_seen_at,
            current = p_current,
            updated_at = v_now
        where tracked_vessel_id = v_existing.tracked_vessel_id;
    else
        insert into public.tracked_vessels (
            device_id,
            installation_id,
            vessel_identity,
            vessel_imo,
            vessel_name,
            started_at,
            active,
            stopped_at,
            last_seen_at,
            current,
            created_at,
            updated_at
        )
        values (
            p_device_id,
            p_installation_id,
            p_vessel_identity,
            p_vessel_imo,
            p_vessel_name,
            v_now,
            true,
            null,
            p_last_seen_at,
            p_current,
            v_now,
            v_now
        );
    end if;

    return query
    select *
    from public.tracked_vessels tv
    where tv.installation_id = p_installation_id
      and tv.vessel_identity = p_vessel_identity;
end;
$$;

create or replace function public.deactivate_tracked_vessel(
    p_device_id text,
    p_installation_id uuid,
    p_tracked_vessel_id uuid
)
returns setof public.tracked_vessels
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := clock_timestamp();
begin
    update public.tracked_vessels
    set
        active = false,
        stopped_at = coalesce(stopped_at, v_now),
        updated_at = v_now
    where tracked_vessel_id = p_tracked_vessel_id
      and device_id = p_device_id
      and installation_id = p_installation_id;

    return query
    select *
    from public.tracked_vessels tv
    where tv.tracked_vessel_id = p_tracked_vessel_id
      and tv.device_id = p_device_id
      and tv.installation_id = p_installation_id;
end;
$$;

create or replace function public.revoke_mobile_installation(
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
    v_now timestamptz := clock_timestamp();
begin
    update public.tracked_vessels
    set
        active = false,
        stopped_at = coalesce(stopped_at, v_now),
        updated_at = v_now
    where installation_id = p_installation_id
      and device_id = p_device_id
      and active = true;

    update public.mobile_installations
    set
        active = false,
        last_seen_at = v_now,
        revoked_at = v_now
    where installation_id = p_installation_id
      and device_id = p_device_id;

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
        update public.tracked_vessels
        set
            active = false,
            stopped_at = coalesce(stopped_at, v_now),
            updated_at = v_now
        where device_id = p_device_id
          and active = true;

        update public.mobile_installations
        set
            active = false,
            last_seen_at = v_now,
            revoked_at = v_now
        where device_id = p_device_id;

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

revoke all on function public.upsert_tracked_vessel(
    text, uuid, text, text, text, jsonb, timestamptz
) from public, anon, authenticated;
revoke all on function public.deactivate_tracked_vessel(text, uuid, uuid)
    from public, anon, authenticated;
revoke all on function public.revoke_mobile_installation(text, uuid)
    from public, anon, authenticated;
revoke all on function public.rotate_device_view_secret(text, text)
    from public, anon, authenticated;

grant execute on function public.upsert_tracked_vessel(
    text, uuid, text, text, text, jsonb, timestamptz
) to service_role;
grant execute on function public.deactivate_tracked_vessel(text, uuid, uuid)
    to service_role;
grant execute on function public.revoke_mobile_installation(text, uuid)
    to service_role;
grant execute on function public.rotate_device_view_secret(text, text)
    to service_role;
