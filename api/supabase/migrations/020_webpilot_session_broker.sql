-- Migration 020: WebPilot Session Broker for SPEC 027 C2-A.
-- Local/ephemeral validation only until an explicit production migration gate.

create table if not exists public.webpilot_provider_scope_requirements (
    realm_id text primary key references public.webpilot_auth_realms(realm_id),
    scope_id text not null,
    schema_version integer not null,
    capabilities text[] not null default '{}',
    updated_at timestamptz not null default clock_timestamp(),
    constraint webpilot_provider_scope_schema_positive
        check (schema_version > 0),
    constraint webpilot_provider_scope_id_nonempty
        check (length(btrim(scope_id)) > 0)
);

create table if not exists public.webpilot_session_publishers (
    publisher_id uuid primary key,
    realm_id text not null references public.webpilot_auth_realms(realm_id),
    device_id text not null references public.devices(device_id),
    provider_scope_id text not null,
    provider_scope_schema_version integer not null,
    provider_scope_capabilities text[] not null default '{}',
    scope_status text not null default 'unverified',
    scope_verified_at timestamptz,
    last_generation bigint not null default 0,
    status text not null default 'active',
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    revoked_at timestamptz,
    constraint webpilot_session_publishers_scope_schema_positive
        check (provider_scope_schema_version > 0),
    constraint webpilot_session_publishers_scope_status_check
        check (scope_status in ('unverified', 'verified', 'incompatible')),
    constraint webpilot_session_publishers_generation_check
        check (last_generation >= 0),
    constraint webpilot_session_publishers_status_check
        check (status in ('active', 'revoked')),
    constraint webpilot_session_publishers_revoked_check
        check (
            (status = 'active' and revoked_at is null)
            or (status = 'revoked' and revoked_at is not null)
        ),
    constraint webpilot_session_publishers_verified_check
        check (
            (scope_status = 'verified' and scope_verified_at is not null)
            or scope_status <> 'verified'
        )
);

create unique index if not exists webpilot_one_active_publisher_per_device_realm
    on public.webpilot_session_publishers(realm_id, device_id)
    where status = 'active';

create table if not exists public.webpilot_session_leases (
    lease_id uuid primary key,
    realm_id text not null references public.webpilot_auth_realms(realm_id),
    publisher_id uuid not null references public.webpilot_session_publishers(publisher_id),
    local_generation bigint not null,
    realm_epoch bigint not null,
    payload_fingerprint text not null,
    ciphertext text not null,
    nonce text not null,
    key_version integer not null,
    payload_schema_version integer not null,
    received_at timestamptz not null default clock_timestamp(),
    expires_at timestamptz,
    status text not null default 'accepted',
    revoked_at timestamptz,
    invalidated_at timestamptz,
    constraint webpilot_session_leases_generation_check
        check (local_generation > 0),
    constraint webpilot_session_leases_epoch_check
        check (realm_epoch > 0),
    constraint webpilot_session_leases_fingerprint_check
        check (length(payload_fingerprint) = 64),
    constraint webpilot_session_leases_key_version_check
        check (key_version > 0),
    constraint webpilot_session_leases_payload_schema_check
        check (payload_schema_version > 0),
    constraint webpilot_session_leases_status_check
        check (status in ('accepted', 'revoked', 'invalidated')),
    constraint webpilot_session_leases_status_time_check
        check (
            (status = 'accepted' and revoked_at is null and invalidated_at is null)
            or (status = 'revoked' and revoked_at is not null and invalidated_at is null)
            or (status = 'invalidated' and invalidated_at is not null and revoked_at is null)
        ),
    unique (publisher_id, local_generation),
    unique (realm_id, realm_epoch)
);

create table if not exists public.webpilot_realm_epoch_counters (
    realm_id text primary key references public.webpilot_auth_realms(realm_id),
    last_epoch bigint not null default 0,
    constraint webpilot_realm_epoch_counter_check check (last_epoch >= 0)
);

alter table public.webpilot_provider_scope_requirements enable row level security;
alter table public.webpilot_session_publishers enable row level security;
alter table public.webpilot_session_leases enable row level security;
alter table public.webpilot_realm_epoch_counters enable row level security;

revoke all on table public.webpilot_provider_scope_requirements from anon, authenticated;
revoke all on table public.webpilot_session_publishers from anon, authenticated;
revoke all on table public.webpilot_session_leases from anon, authenticated;
revoke all on table public.webpilot_realm_epoch_counters from anon, authenticated;

create or replace function public.set_required_provider_scope(
    p_realm_id text,
    p_scope_id text,
    p_schema_version integer,
    p_capabilities text[]
)
returns table (
    realm_id text,
    scope_id text,
    schema_version integer,
    capabilities text[],
    updated_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_realm_active boolean;
begin
    select r.active
    into v_realm_active
    from public.webpilot_auth_realms r
    where r.realm_id = p_realm_id
    for update;

    if not found then
        return;
    end if;

    insert into public.webpilot_provider_scope_requirements (
        realm_id, scope_id, schema_version, capabilities, updated_at
    )
    values (
        p_realm_id,
        p_scope_id,
        p_schema_version,
        coalesce(p_capabilities, '{}'::text[]),
        clock_timestamp()
    )
    on conflict on constraint webpilot_provider_scope_requirements_pkey do update
    set
        scope_id = excluded.scope_id,
        schema_version = excluded.schema_version,
        capabilities = excluded.capabilities,
        updated_at = case
            when public.webpilot_provider_scope_requirements.scope_id
                    is distinct from excluded.scope_id
              or public.webpilot_provider_scope_requirements.schema_version
                    is distinct from excluded.schema_version
              or public.webpilot_provider_scope_requirements.capabilities
                    is distinct from excluded.capabilities
                then clock_timestamp()
            else public.webpilot_provider_scope_requirements.updated_at
        end;

    update public.webpilot_session_publishers p
    set
        scope_status = 'incompatible',
        scope_verified_at = null,
        updated_at = clock_timestamp()
    where p.realm_id = p_realm_id
      and p.status = 'active'
      and p.scope_status = 'verified'
      and (
          p.provider_scope_id is distinct from p_scope_id
          or p.provider_scope_schema_version is distinct from p_schema_version
          or p.provider_scope_capabilities
                is distinct from coalesce(p_capabilities, '{}'::text[])
      );

    return query
    select s.realm_id, s.scope_id, s.schema_version, s.capabilities, s.updated_at
    from public.webpilot_provider_scope_requirements s
    where s.realm_id = p_realm_id;
end;
$$;

create or replace function public.ensure_session_publisher(
    p_device_id text,
    p_realm_id text,
    p_publisher_id uuid,
    p_scope_id text,
    p_scope_schema_version integer,
    p_scope_capabilities text[]
)
returns table (
    publisher_id uuid,
    realm_id text,
    device_id text,
    provider_scope_id text,
    provider_scope_schema_version integer,
    provider_scope_capabilities text[],
    scope_status text,
    scope_verified_at timestamptz,
    last_generation bigint,
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
    v_device_enabled boolean;
    v_realm_active boolean;
    v_membership_revoked_at timestamptz;
    v_existing public.webpilot_session_publishers%rowtype;
    v_now timestamptz := clock_timestamp();
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

    select p.*
    into v_existing
    from public.webpilot_session_publishers p
    where p.publisher_id = p_publisher_id
    for update;

    if found then
        if v_existing.device_id <> p_device_id
           or v_existing.realm_id <> p_realm_id
           or v_existing.status <> 'active' then
            raise exception 'session_publisher_conflict';
        end if;

        if v_existing.provider_scope_id is distinct from p_scope_id
           or v_existing.provider_scope_schema_version
                is distinct from p_scope_schema_version
           or v_existing.provider_scope_capabilities
                is distinct from coalesce(p_scope_capabilities, '{}'::text[]) then
            update public.webpilot_session_publishers p
            set
                provider_scope_id = p_scope_id,
                provider_scope_schema_version = p_scope_schema_version,
                provider_scope_capabilities =
                    coalesce(p_scope_capabilities, '{}'::text[]),
                scope_status = 'unverified',
                scope_verified_at = null,
                updated_at = v_now
            where p.publisher_id = p_publisher_id
            returning p.* into v_existing;
        end if;

        return query select
            v_existing.publisher_id, v_existing.realm_id,
            v_existing.device_id, v_existing.provider_scope_id,
            v_existing.provider_scope_schema_version,
            v_existing.provider_scope_capabilities,
            v_existing.scope_status, v_existing.scope_verified_at,
            v_existing.last_generation, v_existing.status,
            v_existing.created_at, v_existing.updated_at,
            v_existing.revoked_at;
        return;
    end if;

    update public.webpilot_session_publishers p
    set
        status = 'revoked',
        revoked_at = v_now,
        updated_at = v_now
    where p.realm_id = p_realm_id
      and p.device_id = p_device_id
      and p.status = 'active';

    insert into public.webpilot_session_publishers (
        publisher_id,
        realm_id,
        device_id,
        provider_scope_id,
        provider_scope_schema_version,
        provider_scope_capabilities,
        scope_status,
        scope_verified_at,
        last_generation,
        status
    )
    values (
        p_publisher_id,
        p_realm_id,
        p_device_id,
        p_scope_id,
        p_scope_schema_version,
        coalesce(p_scope_capabilities, '{}'::text[]),
        'unverified',
        null,
        0,
        'active'
    )
    returning * into v_existing;

    return query select
        v_existing.publisher_id, v_existing.realm_id,
        v_existing.device_id, v_existing.provider_scope_id,
        v_existing.provider_scope_schema_version,
        v_existing.provider_scope_capabilities,
        v_existing.scope_status, v_existing.scope_verified_at,
        v_existing.last_generation, v_existing.status,
        v_existing.created_at, v_existing.updated_at,
        v_existing.revoked_at;
end;
$$;

create or replace function public.verify_session_publisher_scope(
    p_publisher_id uuid
)
returns table (
    publisher_id uuid,
    realm_id text,
    device_id text,
    provider_scope_id text,
    provider_scope_schema_version integer,
    provider_scope_capabilities text[],
    scope_status text,
    scope_verified_at timestamptz,
    last_generation bigint,
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
    v_publisher public.webpilot_session_publishers%rowtype;
    v_required public.webpilot_provider_scope_requirements%rowtype;
    v_status text;
    v_now timestamptz := clock_timestamp();
begin
    select p.*
    into v_publisher
    from public.webpilot_session_publishers p
    where p.publisher_id = p_publisher_id
    for update;

    if not found then
        return;
    end if;

    if v_publisher.status <> 'active' then
        return query select
            v_publisher.publisher_id, v_publisher.realm_id,
            v_publisher.device_id, v_publisher.provider_scope_id,
            v_publisher.provider_scope_schema_version,
            v_publisher.provider_scope_capabilities,
            v_publisher.scope_status, v_publisher.scope_verified_at,
            v_publisher.last_generation, v_publisher.status,
            v_publisher.created_at, v_publisher.updated_at,
            v_publisher.revoked_at;
        return;
    end if;

    select s.*
    into v_required
    from public.webpilot_provider_scope_requirements s
    where s.realm_id = v_publisher.realm_id
    for update;

    v_status := case
        when found
         and v_required.scope_id = v_publisher.provider_scope_id
         and v_required.schema_version = v_publisher.provider_scope_schema_version
         and v_required.capabilities = v_publisher.provider_scope_capabilities
        then 'verified'
        else 'incompatible'
    end;

    update public.webpilot_session_publishers p
    set
        scope_status = v_status,
        scope_verified_at = case when v_status = 'verified' then v_now else null end,
        updated_at = v_now
    where p.publisher_id = p_publisher_id
    returning p.* into v_publisher;

    return query select
        v_publisher.publisher_id, v_publisher.realm_id,
        v_publisher.device_id, v_publisher.provider_scope_id,
        v_publisher.provider_scope_schema_version,
        v_publisher.provider_scope_capabilities,
        v_publisher.scope_status, v_publisher.scope_verified_at,
        v_publisher.last_generation, v_publisher.status,
        v_publisher.created_at, v_publisher.updated_at,
        v_publisher.revoked_at;
end;
$$;

create or replace function public.revoke_session_publisher(
    p_publisher_id uuid
)
returns table (
    publisher_id uuid,
    realm_id text,
    device_id text,
    provider_scope_id text,
    provider_scope_schema_version integer,
    provider_scope_capabilities text[],
    scope_status text,
    scope_verified_at timestamptz,
    last_generation bigint,
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
    v_publisher public.webpilot_session_publishers%rowtype;
    v_now timestamptz := clock_timestamp();
begin
    select p.*
    into v_publisher
    from public.webpilot_session_publishers p
    where p.publisher_id = p_publisher_id
    for update;

    if not found then
        return;
    end if;

    if v_publisher.status = 'active' then
        update public.webpilot_session_publishers p
        set
            status = 'revoked',
            revoked_at = v_now,
            updated_at = v_now
        where p.publisher_id = p_publisher_id
        returning p.* into v_publisher;
    end if;

    return query select
        v_publisher.publisher_id, v_publisher.realm_id,
        v_publisher.device_id, v_publisher.provider_scope_id,
        v_publisher.provider_scope_schema_version,
        v_publisher.provider_scope_capabilities,
        v_publisher.scope_status, v_publisher.scope_verified_at,
        v_publisher.last_generation, v_publisher.status,
        v_publisher.created_at, v_publisher.updated_at,
        v_publisher.revoked_at;
end;
$$;

create or replace function public.accept_session_lease(
    p_device_id text,
    p_realm_id text,
    p_publisher_id uuid,
    p_lease_id uuid,
    p_local_generation bigint,
    p_payload_fingerprint text,
    p_ciphertext text,
    p_nonce text,
    p_key_version integer,
    p_payload_schema_version integer,
    p_expires_at timestamptz
)
returns table (
    lease_id uuid,
    realm_id text,
    publisher_id uuid,
    local_generation bigint,
    realm_epoch bigint,
    payload_fingerprint text,
    ciphertext text,
    nonce text,
    key_version integer,
    payload_schema_version integer,
    received_at timestamptz,
    expires_at timestamptz,
    status text,
    revoked_at timestamptz,
    invalidated_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_device_enabled boolean;
    v_realm_active boolean;
    v_membership_revoked_at timestamptz;
    v_publisher public.webpilot_session_publishers%rowtype;
    v_required public.webpilot_provider_scope_requirements%rowtype;
    v_existing public.webpilot_session_leases%rowtype;
    v_epoch bigint;
    v_inserted public.webpilot_session_leases%rowtype;
begin
    select d.enabled
    into v_device_enabled
    from public.devices d
    where d.device_id = p_device_id
    for update;
    if not found or v_device_enabled is not true then return; end if;

    select r.active
    into v_realm_active
    from public.webpilot_auth_realms r
    where r.realm_id = p_realm_id
    for update;
    if not found or v_realm_active is not true then return; end if;

    select a.revoked_at
    into v_membership_revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = p_realm_id and a.device_id = p_device_id
    for update;
    if not found or v_membership_revoked_at is not null then return; end if;

    select p.*
    into v_publisher
    from public.webpilot_session_publishers p
    where p.publisher_id = p_publisher_id
    for update;

    if not found
       or v_publisher.device_id <> p_device_id
       or v_publisher.realm_id <> p_realm_id
       or v_publisher.status <> 'active'
       or v_publisher.scope_status <> 'verified' then
        return;
    end if;

    select s.*
    into v_required
    from public.webpilot_provider_scope_requirements s
    where s.realm_id = p_realm_id
    for update;

    if not found
       or v_required.scope_id <> v_publisher.provider_scope_id
       or v_required.schema_version <> v_publisher.provider_scope_schema_version
       or v_required.capabilities <> v_publisher.provider_scope_capabilities then
        return;
    end if;

    select l.*
    into v_existing
    from public.webpilot_session_leases l
    where l.publisher_id = p_publisher_id
      and l.local_generation = p_local_generation
    for update;

    if found then
        if v_existing.status <> 'accepted' then
            raise exception 'session_lease_replay';
        end if;
        if v_existing.payload_fingerprint <> p_payload_fingerprint then
            raise exception 'session_lease_generation_conflict';
        end if;
        return query select
            v_existing.lease_id, v_existing.realm_id,
            v_existing.publisher_id, v_existing.local_generation,
            v_existing.realm_epoch, v_existing.payload_fingerprint,
            v_existing.ciphertext, v_existing.nonce,
            v_existing.key_version, v_existing.payload_schema_version,
            v_existing.received_at, v_existing.expires_at,
            v_existing.status, v_existing.revoked_at,
            v_existing.invalidated_at;
        return;
    end if;

    if p_local_generation <= v_publisher.last_generation then
        raise exception 'session_lease_replay';
    end if;

    insert into public.webpilot_realm_epoch_counters as c (
        realm_id, last_epoch
    )
    values (p_realm_id, 1)
    on conflict on constraint webpilot_realm_epoch_counters_pkey do update
    set last_epoch = c.last_epoch + 1
    returning last_epoch into v_epoch;

    insert into public.webpilot_session_leases (
        lease_id, realm_id, publisher_id, local_generation, realm_epoch,
        payload_fingerprint, ciphertext, nonce, key_version,
        payload_schema_version, expires_at, status
    )
    values (
        p_lease_id, p_realm_id, p_publisher_id, p_local_generation, v_epoch,
        p_payload_fingerprint, p_ciphertext, p_nonce, p_key_version,
        p_payload_schema_version, p_expires_at, 'accepted'
    )
    returning * into v_inserted;

    update public.webpilot_session_publishers p
    set
        last_generation = p_local_generation,
        updated_at = clock_timestamp()
    where p.publisher_id = p_publisher_id;

    return query select
        v_inserted.lease_id, v_inserted.realm_id,
        v_inserted.publisher_id, v_inserted.local_generation,
        v_inserted.realm_epoch, v_inserted.payload_fingerprint,
        v_inserted.ciphertext, v_inserted.nonce,
        v_inserted.key_version, v_inserted.payload_schema_version,
        v_inserted.received_at, v_inserted.expires_at,
        v_inserted.status, v_inserted.revoked_at,
        v_inserted.invalidated_at;
end;
$$;

create or replace function public.revoke_session_lease(
    p_device_id text,
    p_realm_id text,
    p_lease_id uuid
)
returns setof public.webpilot_session_leases
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_device_enabled boolean;
    v_realm_active boolean;
    v_membership_revoked_at timestamptz;
    v_lease public.webpilot_session_leases%rowtype;
begin
    select d.enabled into v_device_enabled
    from public.devices d where d.device_id = p_device_id for update;
    if not found or v_device_enabled is not true then return; end if;

    select r.active into v_realm_active
    from public.webpilot_auth_realms r where r.realm_id = p_realm_id for update;
    if not found or v_realm_active is not true then return; end if;

    select a.revoked_at into v_membership_revoked_at
    from public.webpilot_auth_realm_devices a
    where a.realm_id = p_realm_id and a.device_id = p_device_id
    for update;
    if not found or v_membership_revoked_at is not null then return; end if;

    select l.*
    into v_lease
    from public.webpilot_session_leases l
    join public.webpilot_session_publishers p
      on p.publisher_id = l.publisher_id
    where l.lease_id = p_lease_id
      and l.realm_id = p_realm_id
      and p.device_id = p_device_id
    for update of l;

    if not found then return; end if;

    if v_lease.status = 'accepted' then
        update public.webpilot_session_leases l
        set status = 'revoked', revoked_at = clock_timestamp()
        where l.lease_id = p_lease_id
        returning l.* into v_lease;
    end if;

    return next v_lease;
end;
$$;

create or replace function public.invalidate_session_lease(
    p_realm_id text,
    p_lease_id uuid,
    p_realm_epoch bigint
)
returns setof public.webpilot_session_leases
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_lease public.webpilot_session_leases%rowtype;
begin
    select l.*
    into v_lease
    from public.webpilot_session_leases l
    where l.lease_id = p_lease_id
      and l.realm_id = p_realm_id
      and l.realm_epoch = p_realm_epoch
    for update;

    if not found then return; end if;

    if v_lease.status = 'accepted' then
        update public.webpilot_session_leases l
        set status = 'invalidated', invalidated_at = clock_timestamp()
        where l.lease_id = p_lease_id
        returning l.* into v_lease;
    end if;

    return next v_lease;
end;
$$;

create or replace function public.get_current_session_lease(
    p_realm_id text,
    p_now timestamptz
)
returns setof public.webpilot_session_leases
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
    select l.*
    from public.webpilot_session_leases l
    join public.webpilot_session_publishers p
      on p.publisher_id = l.publisher_id
    join public.webpilot_provider_scope_requirements s
      on s.realm_id = l.realm_id
    join public.devices d
      on d.device_id = p.device_id
    join public.webpilot_auth_realms r
      on r.realm_id = l.realm_id
    join public.webpilot_auth_realm_devices a
      on a.realm_id = l.realm_id and a.device_id = p.device_id
    where l.realm_id = p_realm_id
      and l.status = 'accepted'
      and (l.expires_at is null or l.expires_at > p_now)
      and p.status = 'active'
      and p.scope_status = 'verified'
      and p.provider_scope_id = s.scope_id
      and p.provider_scope_schema_version = s.schema_version
      and p.provider_scope_capabilities = s.capabilities
      and d.enabled = true
      and r.active = true
      and a.revoked_at is null
    order by l.realm_epoch desc
    limit 1;
$$;

revoke all on function public.set_required_provider_scope(text, text, integer, text[])
    from public, anon, authenticated;
revoke all on function public.ensure_session_publisher(text, text, uuid, text, integer, text[])
    from public, anon, authenticated;
revoke all on function public.verify_session_publisher_scope(uuid)
    from public, anon, authenticated;
revoke all on function public.revoke_session_publisher(uuid)
    from public, anon, authenticated;
revoke all on function public.accept_session_lease(
    text, text, uuid, uuid, bigint, text, text, text, integer, integer, timestamptz
) from public, anon, authenticated;
revoke all on function public.revoke_session_lease(text, text, uuid)
    from public, anon, authenticated;
revoke all on function public.invalidate_session_lease(text, uuid, bigint)
    from public, anon, authenticated;
revoke all on function public.get_current_session_lease(text, timestamptz)
    from public, anon, authenticated;

grant execute on function public.set_required_provider_scope(text, text, integer, text[])
    to service_role;
grant execute on function public.ensure_session_publisher(text, text, uuid, text, integer, text[])
    to service_role;
grant execute on function public.verify_session_publisher_scope(uuid)
    to service_role;
grant execute on function public.revoke_session_publisher(uuid)
    to service_role;
grant execute on function public.accept_session_lease(
    text, text, uuid, uuid, bigint, text, text, text, integer, integer, timestamptz
) to service_role;
grant execute on function public.revoke_session_lease(text, text, uuid)
    to service_role;
grant execute on function public.invalidate_session_lease(text, uuid, bigint)
    to service_role;
grant execute on function public.get_current_session_lease(text, timestamptz)
    to service_role;
