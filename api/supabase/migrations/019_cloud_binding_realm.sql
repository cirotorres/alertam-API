-- Migration 019: CloudBinding realm authority for SPEC 027 C1-B.
-- Local/ephemeral validation only until an explicit production migration gate.

create table if not exists public.webpilot_auth_realms (
    realm_id text primary key,
    active boolean not null default true,
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp()
);

create table if not exists public.webpilot_auth_realm_devices (
    realm_id text not null references public.webpilot_auth_realms(realm_id),
    device_id text not null references public.devices(device_id),
    authorized_at timestamptz not null default clock_timestamp(),
    revoked_at timestamptz,
    primary key (realm_id, device_id),
    constraint webpilot_auth_realm_devices_time_check
        check (revoked_at is null or revoked_at >= authorized_at)
);

create table if not exists public.cloud_bindings (
    cloud_binding_id uuid primary key default gen_random_uuid(),
    lifecycle_order bigint generated always as identity unique,
    device_id text not null references public.devices(device_id),
    realm_id text not null references public.webpilot_auth_realms(realm_id),
    credential_hash text not null,
    credential_version integer not null default 1,
    status text not null default 'active',
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    revoked_at timestamptz,
    constraint cloud_bindings_version_check check (credential_version > 0),
    constraint cloud_bindings_status_check check (status in ('active', 'revoked')),
    constraint cloud_bindings_status_revoked_at_check check (
        (status = 'active' and revoked_at is null)
        or (status = 'revoked' and revoked_at is not null)
    )
);

create unique index if not exists cloud_bindings_one_active_per_device
    on public.cloud_bindings(device_id)
    where status = 'active';

alter table public.webpilot_auth_realms enable row level security;
alter table public.webpilot_auth_realm_devices enable row level security;
alter table public.cloud_bindings enable row level security;

revoke all on table public.webpilot_auth_realms from anon, authenticated;
revoke all on table public.webpilot_auth_realm_devices from anon, authenticated;
revoke all on table public.cloud_bindings from anon, authenticated;

create or replace function public.authorize_realm_device(
    p_realm_id text,
    p_device_id text
)
returns table (
    realm_id text,
    device_id text,
    authorized_at timestamptz,
    revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_now timestamptz := clock_timestamp();
begin
    if not exists (
        select 1 from public.webpilot_auth_realms r
        where r.realm_id = p_realm_id
    ) or not exists (
        select 1 from public.devices d
        where d.device_id = p_device_id
    ) then
        return;
    end if;

    insert into public.webpilot_auth_realm_devices (
        realm_id, device_id, authorized_at, revoked_at
    )
    values (p_realm_id, p_device_id, v_now, null)
    on conflict on constraint webpilot_auth_realm_devices_pkey do update
    set
        authorized_at = case
            when public.webpilot_auth_realm_devices.revoked_at is null
                then public.webpilot_auth_realm_devices.authorized_at
            else excluded.authorized_at
        end,
        revoked_at = null;

    return query
    select a.realm_id, a.device_id, a.authorized_at, a.revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = p_realm_id and a.device_id = p_device_id;
end;
$$;

create or replace function public.revoke_realm_device(
    p_realm_id text,
    p_device_id text
)
returns table (
    realm_id text,
    device_id text,
    authorized_at timestamptz,
    revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_now timestamptz := clock_timestamp();
begin
    update public.webpilot_auth_realm_devices a
    set revoked_at = coalesce(a.revoked_at, v_now)
    where a.realm_id = p_realm_id and a.device_id = p_device_id;

    return query
    select a.realm_id, a.device_id, a.authorized_at, a.revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = p_realm_id and a.device_id = p_device_id;
end;
$$;

create or replace function public.set_webpilot_auth_realm_active(
    p_realm_id text,
    p_active boolean
)
returns table (
    realm_id text,
    active boolean,
    created_at timestamptz,
    updated_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    update public.webpilot_auth_realms r
    set
        active = p_active,
        updated_at = case
            when r.active is distinct from p_active then clock_timestamp()
            else r.updated_at
        end
    where r.realm_id = p_realm_id;

    return query
    select r.realm_id, r.active, r.created_at, r.updated_at
    from public.webpilot_auth_realms r
    where r.realm_id = p_realm_id;
end;
$$;

create or replace function public.ensure_cloud_binding(
    p_device_id text,
    p_realm_id text,
    p_credential_hash text
)
returns table (
    cloud_binding_id uuid,
    device_id text,
    realm_id text,
    credential_hash text,
    credential_version integer,
    status text,
    created_at timestamptz,
    updated_at timestamptz,
    revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_current public.cloud_bindings%rowtype;
    v_new public.cloud_bindings%rowtype;
    v_device_enabled boolean;
    v_realm_active boolean;
    v_membership_revoked_at timestamptz;
begin
    select d.enabled
    into v_device_enabled
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found or v_device_enabled is not true then
        return;
    end if;

    select r.active
    into v_realm_active
    from public.webpilot_auth_realms r
    where r.realm_id = p_realm_id
    for update;

    if not found or v_realm_active is not true then
        return;
    end if;

    select a.revoked_at
    into v_membership_revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = p_realm_id
      and a.device_id = p_device_id
    for update;

    if not found or v_membership_revoked_at is not null then
        return;
    end if;

    select *
    into v_current
    from public.cloud_bindings b
    where b.device_id = p_device_id and b.status = 'active'
    for update;

    if found then
        if v_current.realm_id = p_realm_id
           and v_current.credential_hash = p_credential_hash then
            return query select
                v_current.cloud_binding_id, v_current.device_id,
                v_current.realm_id, v_current.credential_hash,
                v_current.credential_version, v_current.status,
                v_current.created_at, v_current.updated_at,
                v_current.revoked_at;
            return;
        end if;
        raise exception 'cloud_binding_conflict';
    end if;

    begin
        insert into public.cloud_bindings (
            device_id, realm_id, credential_hash
        )
        values (p_device_id, p_realm_id, p_credential_hash)
        returning * into v_new;
    exception when unique_violation then
        select *
        into v_current
        from public.cloud_bindings b
        where b.device_id = p_device_id and b.status = 'active'
        for update;

        if found
           and v_current.realm_id = p_realm_id
           and v_current.credential_hash = p_credential_hash then
            return query select
                v_current.cloud_binding_id, v_current.device_id,
                v_current.realm_id, v_current.credential_hash,
                v_current.credential_version, v_current.status,
                v_current.created_at, v_current.updated_at,
                v_current.revoked_at;
            return;
        end if;

        raise exception 'cloud_binding_conflict';
    end;

    return query select
        v_new.cloud_binding_id, v_new.device_id, v_new.realm_id,
        v_new.credential_hash, v_new.credential_version, v_new.status,
        v_new.created_at, v_new.updated_at, v_new.revoked_at;
end;
$$;

create or replace function public.rotate_cloud_binding(
    p_device_id text,
    p_credential_hash text
)
returns table (
    cloud_binding_id uuid,
    device_id text,
    realm_id text,
    credential_hash text,
    credential_version integer,
    status text,
    created_at timestamptz,
    updated_at timestamptz,
    revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_current public.cloud_bindings%rowtype;
    v_device_enabled boolean;
    v_realm_active boolean;
    v_membership_revoked_at timestamptz;
begin
    select d.enabled
    into v_device_enabled
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found or v_device_enabled is not true then
        return;
    end if;

    select b.*
    into v_current
    from public.cloud_bindings b
    where b.device_id = p_device_id
      and b.status = 'active'
    for update;

    if not found then
        return;
    end if;

    select r.active
    into v_realm_active
    from public.webpilot_auth_realms r
    where r.realm_id = v_current.realm_id
    for update;

    if not found or v_realm_active is not true then
        return;
    end if;

    select a.revoked_at
    into v_membership_revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = v_current.realm_id
      and a.device_id = p_device_id
    for update;

    if not found or v_membership_revoked_at is not null then
        return;
    end if;

    if v_current.credential_hash <> p_credential_hash then
        update public.cloud_bindings b
        set
            credential_hash = p_credential_hash,
            credential_version = b.credential_version + 1,
            updated_at = clock_timestamp()
        where b.cloud_binding_id = v_current.cloud_binding_id
        returning * into v_current;
    end if;

    return query select
        v_current.cloud_binding_id, v_current.device_id, v_current.realm_id,
        v_current.credential_hash, v_current.credential_version,
        v_current.status, v_current.created_at, v_current.updated_at,
        v_current.revoked_at;
end;
$$;

create or replace function public.revoke_cloud_binding(
    p_device_id text
)
returns table (
    cloud_binding_id uuid,
    device_id text,
    realm_id text,
    credential_hash text,
    credential_version integer,
    status text,
    created_at timestamptz,
    updated_at timestamptz,
    revoked_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_current public.cloud_bindings%rowtype;
    v_device_enabled boolean;
    v_realm_active boolean;
    v_membership_revoked_at timestamptz;
    v_was_active boolean := false;
begin
    select d.enabled
    into v_device_enabled
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found or v_device_enabled is not true then
        return;
    end if;

    select b.*
    into v_current
    from public.cloud_bindings b
    where b.device_id = p_device_id
      and b.status = 'active'
    for update;

    if found then
        v_was_active := true;
    else
        select b.*
        into v_current
        from public.cloud_bindings b
        where b.device_id = p_device_id
          and b.status = 'revoked'
        order by b.lifecycle_order desc
        limit 1
        for update;

        if not found then
            return;
        end if;
    end if;

    select r.active
    into v_realm_active
    from public.webpilot_auth_realms r
    where r.realm_id = v_current.realm_id
    for update;

    if not found or v_realm_active is not true then
        return;
    end if;

    select a.revoked_at
    into v_membership_revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = v_current.realm_id
      and a.device_id = p_device_id
    for update;

    if not found or v_membership_revoked_at is not null then
        return;
    end if;

    if v_was_active then
        update public.cloud_bindings b
        set
            status = 'revoked',
            revoked_at = clock_timestamp(),
            updated_at = clock_timestamp()
        where b.cloud_binding_id = v_current.cloud_binding_id
        returning * into v_current;
    end if;

    return query select
        v_current.cloud_binding_id, v_current.device_id, v_current.realm_id,
        v_current.credential_hash, v_current.credential_version,
        v_current.status, v_current.created_at, v_current.updated_at,
        v_current.revoked_at;
end;
$$;

create or replace function public.get_cloud_binding_authority(
    p_cloud_binding_id uuid
)
returns table (
    cloud_binding_id uuid,
    device_id text,
    realm_id text,
    credential_hash text,
    status text,
    device_enabled boolean,
    realm_active boolean,
    membership_active boolean
)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
    select
        b.cloud_binding_id,
        b.device_id,
        b.realm_id,
        b.credential_hash,
        b.status,
        d.enabled,
        r.active,
        (
            a.device_id is not null
            and a.revoked_at is null
        ) as membership_active
    from public.cloud_bindings b
    join public.devices d
      on d.device_id = b.device_id
    join public.webpilot_auth_realms r
      on r.realm_id = b.realm_id
    left join public.webpilot_auth_realm_devices a
      on a.realm_id = b.realm_id
     and a.device_id = b.device_id
    where b.cloud_binding_id = p_cloud_binding_id;
$$;

revoke all on function public.get_cloud_binding_authority(uuid)
    from public, anon, authenticated;

revoke all on function public.authorize_realm_device(text, text)
    from public, anon, authenticated;
revoke all on function public.revoke_realm_device(text, text)
    from public, anon, authenticated;
revoke all on function public.set_webpilot_auth_realm_active(text, boolean)
    from public, anon, authenticated;
revoke all on function public.ensure_cloud_binding(text, text, text)
    from public, anon, authenticated;
revoke all on function public.rotate_cloud_binding(text, text)
    from public, anon, authenticated;
revoke all on function public.revoke_cloud_binding(text)
    from public, anon, authenticated;

grant execute on function public.get_cloud_binding_authority(uuid)
    to service_role;
grant execute on function public.authorize_realm_device(text, text)
    to service_role;
grant execute on function public.revoke_realm_device(text, text)
    to service_role;
grant execute on function public.set_webpilot_auth_realm_active(text, boolean)
    to service_role;
grant execute on function public.ensure_cloud_binding(text, text, text)
    to service_role;
grant execute on function public.rotate_cloud_binding(text, text)
    to service_role;
grant execute on function public.revoke_cloud_binding(text)
    to service_role;
