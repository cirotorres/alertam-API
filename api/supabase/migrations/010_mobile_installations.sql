create table if not exists public.mobile_installations (
    installation_id uuid primary key,
    device_id text not null references public.devices(device_id) on delete cascade,
    active boolean not null default true,
    created_at timestamptz not null default clock_timestamp(),
    last_seen_at timestamptz not null default clock_timestamp(),
    revoked_at timestamptz null,
    updated_at timestamptz not null default clock_timestamp()
);

create index if not exists mobile_installations_device_active_idx
    on public.mobile_installations (device_id, active);

insert into public.mobile_installations (
    installation_id,
    device_id,
    active,
    created_at,
    last_seen_at,
    revoked_at,
    updated_at
)
select
    pi.installation_id,
    pi.device_id,
    pi.active,
    pi.created_at,
    pi.last_seen_at,
    case when pi.active then null else pi.updated_at end,
    pi.updated_at
from public.push_installations pi
on conflict (installation_id) do nothing;

alter table public.mobile_installations enable row level security;
revoke all on table public.mobile_installations from anon, authenticated;

create or replace function public.ensure_mobile_installation(
    p_device_id text,
    p_installation_id uuid
)
returns setof public.mobile_installations
language plpgsql
security definer
set search_path = public
as $$
declare
    v_existing public.mobile_installations%rowtype;
    v_now timestamptz := clock_timestamp();
begin
    if not exists (
        select 1 from public.devices d where d.device_id = p_device_id
    ) then
        return;
    end if;

    select *
    into v_existing
    from public.mobile_installations mi
    where mi.installation_id = p_installation_id
    for update;

    if found and v_existing.device_id <> p_device_id then
        return;
    end if;

    if not found then
        insert into public.mobile_installations (
            installation_id,
            device_id,
            active,
            created_at,
            last_seen_at,
            revoked_at,
            updated_at
        )
        values (
            p_installation_id,
            p_device_id,
            true,
            v_now,
            v_now,
            null,
            v_now
        );
    else
        update public.mobile_installations
        set
            active = true,
            last_seen_at = v_now,
            revoked_at = null,
            updated_at = v_now
        where installation_id = p_installation_id;
    end if;

    return query
    select *
    from public.mobile_installations mi
    where mi.installation_id = p_installation_id
      and mi.device_id = p_device_id;
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
    update public.mobile_installations
    set
        active = false,
        last_seen_at = v_now,
        revoked_at = v_now,
        updated_at = v_now
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
        update public.mobile_installations
        set
            active = false,
            last_seen_at = v_now,
            revoked_at = v_now,
            updated_at = v_now
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

revoke all on function public.ensure_mobile_installation(text, uuid)
    from public, anon, authenticated;
revoke all on function public.revoke_mobile_installation(text, uuid)
    from public, anon, authenticated;
revoke all on function public.rotate_device_view_secret(text, text)
    from public, anon, authenticated;

grant execute on function public.ensure_mobile_installation(text, uuid)
    to service_role;
grant execute on function public.revoke_mobile_installation(text, uuid)
    to service_role;
grant execute on function public.rotate_device_view_secret(text, text)
    to service_role;
