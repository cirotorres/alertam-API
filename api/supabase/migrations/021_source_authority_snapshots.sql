-- Migration 021: device-scoped source authority and managed snapshot fencing.
-- SPEC 027 C3-B. Local/ephemeral validation only until an explicit production gate.

alter table public.devices
    add column if not exists snapshot_source text null,
    add column if not exists snapshot_authority_epoch bigint null,
    add column if not exists snapshot_authority_lease_id uuid null,
    add column if not exists snapshot_writer_instance_id uuid null;

alter table public.devices
    drop constraint if exists devices_snapshot_source_check,
    add constraint devices_snapshot_source_check
        check (snapshot_source is null or snapshot_source in ('desktop', 'cloud')),
    drop constraint if exists devices_snapshot_authority_metadata_check,
    add constraint devices_snapshot_authority_metadata_check
        check (
            (
                snapshot_source is null
                and snapshot_authority_epoch is null
                and snapshot_authority_lease_id is null
                and snapshot_writer_instance_id is null
            )
            or (
                snapshot_source is not null
                and snapshot_authority_epoch is not null
                and snapshot_authority_epoch > 0
                and snapshot_authority_lease_id is not null
                and snapshot_writer_instance_id is not null
            )
        );

create table if not exists public.device_source_authority (
    device_id text primary key
        references public.devices(device_id) on delete cascade,
    mode text not null default 'legacy',
    active_source text null,
    authority_epoch bigint not null default 0,
    authority_lease_id uuid null,
    holder_instance_id uuid null,
    lease_expires_at timestamptz null,
    granted_at timestamptz null,
    last_renewed_at timestamptz null,
    last_transition_at timestamptz null,
    transition_reason text null,
    last_authoritative_snapshot_at timestamptz null,
    authoritative_snapshot_stale_since timestamptz null,
    cloud_binding_id uuid null
        references public.cloud_bindings(cloud_binding_id),
    realm_id text null
        references public.webpilot_auth_realms(realm_id),
    observed_realm_epoch bigint null,
    updated_at timestamptz not null default clock_timestamp(),
    constraint device_source_authority_mode_check
        check (mode in ('legacy', 'managed')),
    constraint device_source_authority_source_check
        check (active_source is null or active_source in ('desktop', 'cloud')),
    constraint device_source_authority_epoch_check
        check (authority_epoch >= 0),
    constraint device_source_authority_observed_realm_epoch_check
        check (observed_realm_epoch is null or observed_realm_epoch >= 0),
    constraint device_source_authority_grant_state_check
        check (
            (
                mode = 'legacy'
                and active_source is null
                and authority_lease_id is null
                and holder_instance_id is null
                and lease_expires_at is null
                and granted_at is null
                and last_renewed_at is null
                and cloud_binding_id is null
                and realm_id is null
                and observed_realm_epoch is null
            )
            or (
                mode = 'managed'
                and active_source is not null
                and authority_epoch > 0
                and authority_lease_id is not null
                and holder_instance_id is not null
                and lease_expires_at is not null
                and granted_at is not null
                and (
                    (
                        active_source = 'desktop'
                        and cloud_binding_id is null
                        and realm_id is null
                        and observed_realm_epoch is null
                    )
                    or (
                        active_source = 'cloud'
                        and cloud_binding_id is not null
                        and realm_id is not null
                    )
                )
            )
        )
);

create table if not exists public.device_source_heartbeats (
    device_id text not null
        references public.devices(device_id) on delete cascade,
    source text not null,
    instance_id uuid not null,
    last_heartbeat_at timestamptz not null default clock_timestamp(),
    process_healthy boolean not null default true,
    collection_healthy boolean not null default true,
    healthy_since timestamptz null,
    consecutive_healthy integer not null default 0,
    last_collection_ok_at timestamptz null,
    last_reported_generated_at timestamptz null,
    last_candidate_generated_at timestamptz null,
    last_reason_code text null,
    persistent_state_ready boolean null,
    updated_at timestamptz not null default clock_timestamp(),
    primary key (device_id, source, instance_id),
    constraint device_source_heartbeats_source_check
        check (source in ('desktop', 'cloud')),
    constraint device_source_heartbeats_consecutive_check
        check (consecutive_healthy >= 0),
    constraint device_source_heartbeats_persistent_state_check
        check (source = 'cloud' or persistent_state_ready is null)
);

create table if not exists public.device_source_authority_transitions (
    id bigint generated always as identity primary key,
    device_id text not null
        references public.devices(device_id) on delete cascade,
    authority_epoch bigint not null,
    previous_source text null,
    new_source text null,
    previous_instance_id uuid null,
    new_instance_id uuid null,
    reason_code text not null,
    transitioned_at timestamptz not null default clock_timestamp(),
    constraint device_source_transitions_epoch_check
        check (authority_epoch > 0),
    constraint device_source_transitions_previous_source_check
        check (previous_source is null or previous_source in ('desktop', 'cloud')),
    constraint device_source_transitions_new_source_check
        check (new_source is null or new_source in ('desktop', 'cloud'))
);

alter table public.device_source_authority enable row level security;
alter table public.device_source_heartbeats enable row level security;
alter table public.device_source_authority_transitions enable row level security;

revoke all on table public.device_source_authority from anon, authenticated;
revoke all on table public.device_source_heartbeats from anon, authenticated;
revoke all on table public.device_source_authority_transitions from anon, authenticated;

insert into public.device_source_authority(device_id)
select d.device_id
from public.devices d
on conflict (device_id) do nothing;

create or replace function public.ensure_device_source_authority_row()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    insert into public.device_source_authority(device_id)
    values (new.device_id)
    on conflict (device_id) do nothing;
    return new;
end;
$$;

drop trigger if exists ensure_device_source_authority_row on public.devices;
create trigger ensure_device_source_authority_row
after insert on public.devices
for each row execute function public.ensure_device_source_authority_row();

create or replace function public.get_device_source_authority(
    p_device_id text
)
returns setof public.device_source_authority
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
    select a.*
    from public.device_source_authority a
    where a.device_id = p_device_id;
$$;

-- Canonical lock order used by managed writes:
-- device -> CloudBinding (Cloud only) -> realm -> owner membership
-- -> candidate heartbeat (transition/bootstrap only) -> source authority.
-- Snapshot metadata lives on the already-locked devices row.
create or replace function public.managed_snapshot_generated_at_matches(
    p_snapshot jsonb,
    p_generated_at timestamptz
)
returns boolean
language plpgsql
immutable
set search_path = pg_catalog, public
as $$
declare
    v_raw text;
    v_value timestamptz;
begin
    if p_snapshot is null or p_generated_at is null then
        return false;
    end if;

    v_raw := p_snapshot->>'generated_at';
    if v_raw is null
       or v_raw !~ '([zZ]|[+-][0-9]{2}:[0-9]{2})$' then
        return false;
    end if;

    begin
        v_value := v_raw::timestamptz;
    exception when others then
        return false;
    end;

    return v_value = p_generated_at;
end;
$$;

create or replace function public.bootstrap_managed_source_authority(
    p_device_id text
)
returns table (
    status text,
    reason_code text,
    received_at timestamptz,
    device_id text,
    source text,
    authority_epoch bigint,
    authority_lease_id uuid,
    holder_instance_id uuid,
    lease_expires_at timestamptz,
    previous_source text,
    source_transition boolean,
    side_effect_policy text,
    previous_snapshot jsonb
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_device public.devices%rowtype;
    v_heartbeat public.device_source_heartbeats%rowtype;
    v_authority public.device_source_authority%rowtype;
    v_now timestamptz;
    v_epoch bigint;
    v_lease uuid;
begin
    select d.* into v_device
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found then
        return query select
            'rejected'::text, 'snapshot_invalid'::text, null::timestamptz,
            p_device_id, 'desktop'::text, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none'::text, null::jsonb;
        return;
    end if;

    select h.* into v_heartbeat
    from public.device_source_heartbeats h
    where h.device_id = p_device_id and h.source = 'desktop'
      and h.instance_id = v_device.boot_id
    for update;

    select a.* into v_authority
    from public.device_source_authority a
    where a.device_id = p_device_id
    for update;

    if not found then
        return query select
            'rejected'::text, 'db_unavailable'::text, null::timestamptz,
            p_device_id, 'desktop'::text, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none'::text, null::jsonb;
        return;
    end if;

    v_now := clock_timestamp();

    if v_authority.mode <> 'legacy' then
        return query select
            'ineligible'::text, 'legacy_mode'::text, v_device.received_at,
            p_device_id, 'desktop'::text,
            v_authority.authority_epoch, v_authority.authority_lease_id,
            v_authority.holder_instance_id, v_authority.lease_expires_at,
            null::text, false, 'none'::text, null::jsonb;
        return;
    end if;

    if v_authority.authority_epoch <> 0 then
        return query select
            'ineligible'::text, 'bootstrap_not_eligible'::text, v_device.received_at,
            p_device_id, 'desktop'::text, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none'::text, null::jsonb;
        return;
    end if;

    if v_device.enabled is not true then
        return query select
            'ineligible'::text, 'device_disabled'::text, v_device.received_at,
            p_device_id, 'desktop'::text, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none'::text, null::jsonb;
        return;
    end if;

    if v_device.snapshot is null
       or v_device.boot_id is null
       or v_device.sequence is null
       or v_device.received_at is null
       or v_heartbeat.device_id is null
       or v_heartbeat.instance_id <> v_device.boot_id
       or v_heartbeat.process_healthy is not true
       or v_heartbeat.collection_healthy is not true
       or v_heartbeat.last_reason_code is distinct from 'desktop_healthy'
       or v_heartbeat.last_heartbeat_at <= v_now - interval '90 seconds'
       or v_device.received_at <= v_now - interval '120 seconds' then
        return query select
            'ineligible'::text, 'bootstrap_not_eligible'::text, v_device.received_at,
            p_device_id, 'desktop'::text, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none'::text, null::jsonb;
        return;
    end if;

    v_epoch := v_authority.authority_epoch + 1;
    v_lease := gen_random_uuid();

    update public.device_source_authority a
    set mode = 'managed',
        active_source = 'desktop',
        authority_epoch = v_epoch,
        authority_lease_id = v_lease,
        holder_instance_id = v_device.boot_id,
        lease_expires_at = v_now + interval '180 seconds',
        granted_at = v_now,
        last_renewed_at = v_now,
        last_transition_at = v_now,
        transition_reason = 'desktop_healthy',
        last_authoritative_snapshot_at = v_device.received_at,
        authoritative_snapshot_stale_since = null,
        cloud_binding_id = null,
        realm_id = null,
        observed_realm_epoch = null,
        updated_at = v_now
    where a.device_id = p_device_id
    returning a.* into v_authority;

    update public.devices d
    set snapshot_source = 'desktop',
        snapshot_authority_epoch = v_epoch,
        snapshot_authority_lease_id = v_lease,
        snapshot_writer_instance_id = v_device.boot_id,
        updated_at = v_now
    where d.device_id = p_device_id;

    insert into public.device_source_authority_transitions(
        device_id, authority_epoch, previous_source, new_source,
        previous_instance_id, new_instance_id, reason_code, transitioned_at
    ) values (
        p_device_id, v_epoch, null, 'desktop', null, v_device.boot_id,
        'desktop_healthy', v_now
    );

    return query select
        'accepted'::text, 'desktop_healthy'::text, v_device.received_at,
        p_device_id, 'desktop'::text, v_epoch, v_lease, v_device.boot_id,
        v_authority.lease_expires_at, null::text, false, 'none'::text, null::jsonb;
end;
$$;

create or replace function public.accept_managed_snapshot_current_grant(
    p_device_id text,
    p_source text,
    p_authority_epoch bigint,
    p_authority_lease_id uuid,
    p_holder_instance_id uuid,
    p_snapshot jsonb,
    p_snapshot_schema_version integer,
    p_boot_id uuid,
    p_sequence bigint,
    p_generated_at timestamptz
)
returns table (
    status text,
    reason_code text,
    received_at timestamptz,
    device_id text,
    source text,
    authority_epoch bigint,
    authority_lease_id uuid,
    holder_instance_id uuid,
    lease_expires_at timestamptz,
    previous_source text,
    source_transition boolean,
    side_effect_policy text,
    previous_snapshot jsonb
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_pre public.device_source_authority%rowtype;
    v_authority public.device_source_authority%rowtype;
    v_device public.devices%rowtype;
    v_binding public.cloud_bindings%rowtype;
    v_realm public.webpilot_auth_realms%rowtype;
    v_membership public.webpilot_auth_realm_devices%rowtype;
    v_now timestamptz;
    v_observed_realm_epoch bigint;
    v_previous_source text;
    v_previous_snapshot jsonb;
    v_policy text := 'none';
begin
    if p_source not in ('desktop', 'cloud') then
        return query select 'rejected', 'snapshot_invalid', null::timestamptz,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    select a.* into v_pre
    from public.device_source_authority a
    where a.device_id = p_device_id;

    select d.* into v_device
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found then
        return query select 'rejected', 'snapshot_invalid', null::timestamptz,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if p_source = 'cloud' then
        if v_pre.cloud_binding_id is null or v_pre.realm_id is null then
            return query select 'authority_fenced', 'authority_fenced', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;

        select b.* into v_binding
        from public.cloud_bindings b
        where b.cloud_binding_id = v_pre.cloud_binding_id
        for update;

        select r.* into v_realm
        from public.webpilot_auth_realms r
        where r.realm_id = v_pre.realm_id
        for update;

        select m.* into v_membership
        from public.webpilot_auth_realm_devices m
        where m.realm_id = v_pre.realm_id and m.device_id = p_device_id
        for update;
    end if;

    select a.* into v_authority
    from public.device_source_authority a
    where a.device_id = p_device_id
    for update;

    if v_authority.mode <> 'managed'
       or v_authority.active_source is distinct from p_source
       or v_authority.authority_epoch <> p_authority_epoch
       or v_authority.authority_lease_id is distinct from p_authority_lease_id
       or v_authority.holder_instance_id is distinct from p_holder_instance_id
       or p_boot_id is distinct from p_holder_instance_id then
        return query select 'authority_fenced', 'authority_fenced', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    v_now := clock_timestamp();

    if v_device.enabled is not true then
        return query select 'ineligible', 'device_disabled', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if v_authority.lease_expires_at <= v_now then
        return query select 'authority_fenced', 'authority_lease_expired', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if p_source = 'cloud' then
        if v_binding.cloud_binding_id is null
           or v_binding.device_id <> p_device_id
           or v_binding.realm_id <> v_authority.realm_id
           or v_binding.status <> 'active'
           or v_binding.cloud_binding_id <> v_authority.cloud_binding_id then
            return query select 'authority_fenced', 'binding_revoked', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
        if v_realm.realm_id is null or v_realm.active is not true then
            return query select 'authority_fenced', 'realm_inactive', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
        if v_membership.device_id is null or v_membership.revoked_at is not null then
            return query select 'authority_fenced', 'membership_revoked', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;

        select l.realm_epoch into v_observed_realm_epoch
        from public.get_current_session_lease(v_authority.realm_id, v_now) l;
        if not found then
            return query select 'ineligible', 'cloud_auth_unavailable', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
    end if;

    if p_snapshot is null
       or p_sequence <= 0
       or p_snapshot_schema_version not in (1, 2)
       or not (p_snapshot ? 'boot_id')
       or not (p_snapshot ? 'sequence')
       or not (p_snapshot ? 'schema_version')
       or not (p_snapshot ? 'generated_at')
       or p_snapshot->>'boot_id' <> p_boot_id::text
       or p_snapshot->>'sequence' <> p_sequence::text
       or p_snapshot->>'schema_version' <> p_snapshot_schema_version::text
       or not public.managed_snapshot_generated_at_matches(
            p_snapshot, p_generated_at
       ) then
        return query select 'rejected', 'snapshot_invalid', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if p_generated_at > v_now + interval '60 seconds' then
        return query select 'rejected', 'snapshot_clock_ahead', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;
    if p_generated_at < v_now - interval '300 seconds' then
        return query select 'rejected', 'snapshot_too_old', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if v_device.snapshot_authority_epoch is distinct from p_authority_epoch
       or v_device.snapshot_authority_lease_id is distinct from p_authority_lease_id
       or v_device.snapshot_writer_instance_id is distinct from p_holder_instance_id
       or v_device.snapshot_source is distinct from p_source then
        return query select 'authority_fenced', 'authority_fenced', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if v_device.sequence is not null and p_sequence < v_device.sequence then
        return query select 'rejected', 'snapshot_out_of_order', v_device.received_at,
            p_device_id, p_source, p_authority_epoch, p_authority_lease_id,
            p_holder_instance_id, v_authority.lease_expires_at,
            null::text, false, 'none', null::jsonb;
        return;
    end if;

    if v_device.sequence = p_sequence then
        if v_device.snapshot = p_snapshot
           and v_device.snapshot_schema_version = p_snapshot_schema_version
           and v_device.boot_id = p_boot_id
           and v_device.generated_at = p_generated_at then
            return query select 'idempotent', null::text, v_device.received_at,
                p_device_id, p_source, p_authority_epoch, p_authority_lease_id,
                p_holder_instance_id, v_authority.lease_expires_at,
                null::text, false, 'none', null::jsonb;
            return;
        end if;
        return query select 'rejected', 'sequence_reuse_mismatch', v_device.received_at,
            p_device_id, p_source, p_authority_epoch, p_authority_lease_id,
            p_holder_instance_id, v_authority.lease_expires_at,
            null::text, false, 'none', null::jsonb;
        return;
    end if;

    v_previous_source := v_device.snapshot_source;
    v_previous_snapshot := v_device.snapshot;
    if p_source = 'desktop' and v_previous_source = 'desktop' then
        v_policy := 'desktop_continuity';
    end if;
    v_now := clock_timestamp();

    update public.devices d
    set snapshot = p_snapshot,
        snapshot_schema_version = p_snapshot_schema_version,
        boot_id = p_boot_id,
        sequence = p_sequence,
        generated_at = p_generated_at,
        received_at = v_now,
        snapshot_source = p_source,
        snapshot_authority_epoch = p_authority_epoch,
        snapshot_authority_lease_id = p_authority_lease_id,
        snapshot_writer_instance_id = p_holder_instance_id,
        updated_at = v_now
    where d.device_id = p_device_id;

    update public.device_source_authority a
    set last_authoritative_snapshot_at = v_now,
        authoritative_snapshot_stale_since = null,
        observed_realm_epoch = case
            when p_source = 'cloud' then v_observed_realm_epoch
            else null
        end,
        updated_at = v_now
    where a.device_id = p_device_id
    returning a.* into v_authority;

    return query select 'accepted', null::text, v_now,
        p_device_id, p_source, p_authority_epoch, p_authority_lease_id,
        p_holder_instance_id, v_authority.lease_expires_at,
        v_previous_source, false, v_policy,
        case when v_policy = 'desktop_continuity'
            then v_previous_snapshot else null::jsonb end;
end;
$$;

create or replace function public.accept_managed_snapshot_transition_candidate(
    p_device_id text,
    p_source text,
    p_holder_instance_id uuid,
    p_snapshot jsonb,
    p_snapshot_schema_version integer,
    p_boot_id uuid,
    p_sequence bigint,
    p_generated_at timestamptz
)
returns table (
    status text,
    reason_code text,
    received_at timestamptz,
    device_id text,
    source text,
    authority_epoch bigint,
    authority_lease_id uuid,
    holder_instance_id uuid,
    lease_expires_at timestamptz,
    previous_source text,
    source_transition boolean,
    side_effect_policy text,
    previous_snapshot jsonb
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_device public.devices%rowtype;
    v_binding public.cloud_bindings%rowtype;
    v_realm public.webpilot_auth_realms%rowtype;
    v_membership public.webpilot_auth_realm_devices%rowtype;
    v_heartbeat public.device_source_heartbeats%rowtype;
    v_locked_hb public.device_source_heartbeats%rowtype;
    v_pre_authority public.device_source_authority%rowtype;
    v_authority public.device_source_authority%rowtype;
    v_now timestamptz;
    v_observed_realm_epoch bigint;
    v_epoch bigint;
    v_lease uuid;
    v_previous_source text;
    v_previous_instance uuid;
    v_policy text := 'none';
    v_transition boolean := false;
    v_gate_reason text;
    v_gate_fresh boolean := false;
begin
    if p_source not in ('desktop', 'cloud') or p_boot_id is distinct from p_holder_instance_id then
        return query select 'rejected', 'snapshot_invalid', null::timestamptz,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    select d.* into v_device
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found then
        return query select 'rejected', 'snapshot_invalid', null::timestamptz,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if p_source = 'cloud' then
        select b.* into v_binding
        from public.cloud_bindings b
        where b.device_id = p_device_id and b.status = 'active'
        for update;

        if not found then
            return query select 'ineligible', 'cloud_binding_unusable', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;

        select r.* into v_realm
        from public.webpilot_auth_realms r
        where r.realm_id = v_binding.realm_id
        for update;

        select m.* into v_membership
        from public.webpilot_auth_realm_devices m
        where m.realm_id = v_binding.realm_id and m.device_id = p_device_id
        for update;
    end if;

    -- Device lock serializes candidate/holder heartbeat changes. This pre-read
    -- identifies lock keys only; it does NOT decide authority eligibility.
    select a.* into v_pre_authority from public.device_source_authority a
    where a.device_id=p_device_id;
    if v_pre_authority.device_id is null then
        return query select 'ineligible','db_unavailable',v_device.received_at,
            p_device_id,p_source,null::bigint,null::uuid,null::uuid,
            null::timestamptz,null::text,false,'none',null::jsonb;
        return;
    end if;

    -- Acquire both heartbeat locks BEFORE authority, ordered across instances.
    for v_locked_hb in
        select h.* from public.device_source_heartbeats h
        where h.device_id=p_device_id and (
            (h.source=p_source and h.instance_id=p_holder_instance_id)
            or (h.source=v_pre_authority.active_source
                and h.instance_id=v_pre_authority.holder_instance_id)
        )
        order by h.source asc, h.instance_id asc for update
    loop
        if v_locked_hb.source=p_source
           and v_locked_hb.instance_id=p_holder_instance_id then
            v_heartbeat:=v_locked_hb;
        end if;
    end loop;

    select a.* into v_authority
    from public.device_source_authority a
    where a.device_id = p_device_id
    for update;

    if v_authority.device_id is null
       or v_authority.mode is distinct from v_pre_authority.mode
       or v_authority.active_source is distinct from v_pre_authority.active_source
       or v_authority.holder_instance_id is distinct from v_pre_authority.holder_instance_id
       or v_authority.authority_epoch is distinct from v_pre_authority.authority_epoch
       or v_authority.authority_lease_id is distinct from v_pre_authority.authority_lease_id
       or v_authority.updated_at is distinct from v_pre_authority.updated_at then
        return query select 'ineligible','authority_fenced',v_device.received_at,
            p_device_id,p_source,null::bigint,null::uuid,null::uuid,
            null::timestamptz,null::text,false,'none',null::jsonb;
        return;
    end if;

    v_now := clock_timestamp();

    if v_authority.mode <> 'managed' then
        return query select 'ineligible', 'legacy_mode', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if v_device.enabled is not true then
        return query select 'ineligible', 'device_disabled', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    -- C3-B has no approved same-source restart/reacquisition policy.
    -- Fail closed until C3-C defines an explicit gate; transition_candidate
    -- must never turn expiry/restart alone into a fresh epoch/lease.
    if v_heartbeat.device_id is null
       or v_heartbeat.instance_id <> p_holder_instance_id
       or v_heartbeat.process_healthy is not true
       or v_heartbeat.collection_healthy is not true
       or (p_source = 'cloud' and v_heartbeat.persistent_state_ready is not true) then
        return query select 'ineligible',
            case when p_source = 'cloud' then 'cloud_standby_stale' else 'failback_wait_stable' end,
            v_device.received_at, p_device_id, p_source,
            null::bigint, null::uuid, null::uuid, null::timestamptz,
            null::text, false, 'none', null::jsonb;
        return;
    end if;

    if p_source = 'cloud' then
        if v_binding.status <> 'active' then
            return query select 'ineligible', 'binding_revoked', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
        if v_realm.realm_id is null or v_realm.active is not true then
            return query select 'ineligible', 'realm_inactive', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
        if v_membership.device_id is null or v_membership.revoked_at is not null then
            return query select 'ineligible', 'membership_revoked', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
        select l.realm_epoch into v_observed_realm_epoch
        from public.get_current_session_lease(v_binding.realm_id, v_now) l;
        if not found then
            return query select 'ineligible', 'cloud_auth_unavailable', v_device.received_at,
                p_device_id, p_source, null::bigint, null::uuid, null::uuid,
                null::timestamptz, null::text, false, 'none', null::jsonb;
            return;
        end if;
    end if;

    if p_snapshot is null
       or p_sequence <= 0
       or p_snapshot_schema_version not in (1, 2)
       or not (p_snapshot ? 'boot_id')
       or not (p_snapshot ? 'sequence')
       or not (p_snapshot ? 'schema_version')
       or not (p_snapshot ? 'generated_at')
       or p_snapshot->>'boot_id' <> p_boot_id::text
       or p_snapshot->>'sequence' <> p_sequence::text
       or p_snapshot->>'schema_version' <> p_snapshot_schema_version::text
       or not public.managed_snapshot_generated_at_matches(
            p_snapshot, p_generated_at
       ) then
        return query select 'rejected', 'snapshot_invalid', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if p_generated_at > v_now + interval '60 seconds' then
        return query select 'rejected', 'snapshot_clock_ahead', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;
    if p_generated_at < v_now - interval '300 seconds' then
        return query select 'rejected', 'snapshot_too_old', v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    v_gate_reason := case
        when p_source = 'cloud' then 'failover_granted'
        else 'failback_granted'
    end;
    v_gate_fresh := (
        v_heartbeat.last_reason_code = v_gate_reason
        and v_heartbeat.updated_at > v_authority.updated_at
    );

    -- The server computes the gate from timestamped state under the device
    -- transaction lock. Client-supplied heartbeat reasons are never authority.
    v_gate_reason := public.source_candidate_reason(
        p_device_id, p_source, p_holder_instance_id, v_now
    );
    if v_gate_reason not in (
        'failover_granted','failback_granted',
        'desktop_reacquire_granted','cloud_reacquire_granted'
    ) then
        -- Existing C3-B semantic: all denied same-source reacquisitions
        -- are authority_fenced, even when the candidate is unhealthy/stale.
        if v_authority.active_source=p_source then
            v_gate_reason := 'authority_fenced';
        end if;
        return query select 'ineligible', v_gate_reason, v_device.received_at,
            p_device_id, p_source, null::bigint, null::uuid, null::uuid,
            null::timestamptz, null::text, false, 'none', null::jsonb;
        return;
    end if;

    if (
        (p_source='cloud' and p_generated_at < v_now - interval '90 seconds')
        or (p_source='desktop' and p_generated_at < v_now - interval '120 seconds')
    ) then
        return query select 'ineligible',
            case when p_source='cloud' then 'cloud_standby_stale'
                 else 'failback_wait_stable' end,
            v_device.received_at,p_device_id,p_source,
            null::bigint,null::uuid,null::uuid,
            null::timestamptz,null::text,false,'none',null::jsonb;
        return;
    end if;

    v_previous_source := v_device.snapshot_source;
    v_previous_instance := v_authority.holder_instance_id;
    v_epoch := v_authority.authority_epoch + 1;
    v_lease := gen_random_uuid();
    v_now := clock_timestamp();
    v_transition := v_previous_source is not null and v_previous_source <> p_source;
    if p_source = 'desktop' then
        v_policy := 'baseline';
    end if;

    update public.device_source_authority a
    set active_source = p_source,
        authority_epoch = v_epoch,
        authority_lease_id = v_lease,
        holder_instance_id = p_holder_instance_id,
        lease_expires_at = v_now + interval '180 seconds',
        granted_at = v_now,
        last_renewed_at = v_now,
        last_transition_at = v_now,
        transition_reason = v_gate_reason,
        last_authoritative_snapshot_at = v_now,
        authoritative_snapshot_stale_since = null,
        cloud_binding_id = case when p_source = 'cloud' then v_binding.cloud_binding_id else null end,
        realm_id = case when p_source = 'cloud' then v_binding.realm_id else null end,
        observed_realm_epoch = case when p_source = 'cloud' then v_observed_realm_epoch else null end,
        updated_at = v_now
    where a.device_id = p_device_id
    returning a.* into v_authority;

    update public.devices d
    set snapshot = p_snapshot,
        snapshot_schema_version = p_snapshot_schema_version,
        boot_id = p_boot_id,
        sequence = p_sequence,
        generated_at = p_generated_at,
        received_at = v_now,
        snapshot_source = p_source,
        snapshot_authority_epoch = v_epoch,
        snapshot_authority_lease_id = v_lease,
        snapshot_writer_instance_id = p_holder_instance_id,
        updated_at = v_now
    where d.device_id = p_device_id;

    insert into public.device_source_authority_transitions(
        device_id, authority_epoch, previous_source, new_source,
        previous_instance_id, new_instance_id, reason_code, transitioned_at
    ) values (
        p_device_id, v_epoch, v_previous_source, p_source,
        v_previous_instance, p_holder_instance_id,
        v_gate_reason,
        v_now
    );

    return query select 'accepted', v_gate_reason,
        v_now, p_device_id, p_source, v_epoch, v_lease, p_holder_instance_id,
        v_authority.lease_expires_at, v_previous_source, v_transition,
        v_policy, null::jsonb;
end;
$$;

create or replace function public.return_source_authority_to_legacy(
    p_device_id text
)
returns setof public.device_source_authority
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_device public.devices%rowtype;
    v_authority public.device_source_authority%rowtype;
    v_now timestamptz := clock_timestamp();
    v_previous_source text;
    v_previous_instance uuid;
    v_epoch bigint;
begin
    select d.* into v_device
    from public.devices d
    where d.device_id = p_device_id
    for update;
    if not found then return; end if;

    select a.* into v_authority
    from public.device_source_authority a
    where a.device_id = p_device_id
    for update;
    if not found then return; end if;

    if v_authority.mode = 'managed' then
        v_previous_source := v_authority.active_source;
        v_previous_instance := v_authority.holder_instance_id;
        v_epoch := v_authority.authority_epoch + 1;

        update public.device_source_authority a
        set mode = 'legacy',
            active_source = null,
            authority_epoch = v_epoch,
            authority_lease_id = null,
            holder_instance_id = null,
            lease_expires_at = null,
            granted_at = null,
            last_renewed_at = null,
            last_transition_at = v_now,
            transition_reason = 'legacy_mode',
            cloud_binding_id = null,
            realm_id = null,
            observed_realm_epoch = null,
            authoritative_snapshot_stale_since = null,
            updated_at = v_now
        where a.device_id = p_device_id
        returning a.* into v_authority;

        update public.devices d
        set snapshot_source = null,
            snapshot_authority_epoch = null,
            snapshot_authority_lease_id = null,
            snapshot_writer_instance_id = null,
            updated_at = v_now
        where d.device_id = p_device_id;

        insert into public.device_source_authority_transitions(
            device_id, authority_epoch, previous_source, new_source,
            previous_instance_id, new_instance_id, reason_code, transitioned_at
        ) values (
            p_device_id, v_epoch, v_previous_source, null,
            v_previous_instance, null, 'legacy_mode', v_now
        );
    end if;

    return next v_authority;
end;
$$;

-- Narrow administrative fencing. These triggers expire the current grant in-place;
-- re-enabling administrative state never extends or resurrects the old lease.
create or replace function public.fence_source_authority_on_device_disable()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if old.enabled is true and new.enabled is false then
        update public.device_source_authority a
        set lease_expires_at = least(a.lease_expires_at, clock_timestamp()),
            transition_reason = 'device_disabled',
            updated_at = clock_timestamp()
        where a.device_id = new.device_id and a.mode = 'managed';
    end if;
    return new;
end;
$$;

drop trigger if exists fence_source_authority_on_device_disable on public.devices;
create trigger fence_source_authority_on_device_disable
after update of enabled on public.devices
for each row execute function public.fence_source_authority_on_device_disable();

create or replace function public.fence_source_authority_on_binding_revoke()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if old.status = 'active' and new.status = 'revoked' then
        update public.device_source_authority a
        set lease_expires_at = least(a.lease_expires_at, clock_timestamp()),
            transition_reason = 'binding_revoked',
            updated_at = clock_timestamp()
        where a.mode = 'managed'
          and a.active_source = 'cloud'
          and a.device_id = new.device_id
          and a.cloud_binding_id = new.cloud_binding_id;
    end if;
    return new;
end;
$$;

drop trigger if exists fence_source_authority_on_binding_revoke on public.cloud_bindings;
create trigger fence_source_authority_on_binding_revoke
after update of status on public.cloud_bindings
for each row execute function public.fence_source_authority_on_binding_revoke();

create or replace function public.fence_source_authority_on_realm_deactivate()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if old.active is true and new.active is false then
        update public.device_source_authority a
        set lease_expires_at = least(a.lease_expires_at, clock_timestamp()),
            transition_reason = 'realm_inactive',
            updated_at = clock_timestamp()
        where a.mode = 'managed'
          and a.active_source = 'cloud'
          and a.realm_id = new.realm_id;
    end if;
    return new;
end;
$$;

drop trigger if exists fence_source_authority_on_realm_deactivate on public.webpilot_auth_realms;
create trigger fence_source_authority_on_realm_deactivate
after update of active on public.webpilot_auth_realms
for each row execute function public.fence_source_authority_on_realm_deactivate();

create or replace function public.fence_source_authority_on_membership_revoke()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if old.revoked_at is null and new.revoked_at is not null then
        update public.device_source_authority a
        set lease_expires_at = least(a.lease_expires_at, clock_timestamp()),
            transition_reason = 'membership_revoked',
            updated_at = clock_timestamp()
        where a.mode = 'managed'
          and a.active_source = 'cloud'
          and a.device_id = new.device_id
          and a.realm_id = new.realm_id;
    end if;
    return new;
end;
$$;

drop trigger if exists fence_source_authority_on_membership_revoke on public.webpilot_auth_realm_devices;
create trigger fence_source_authority_on_membership_revoke
after update of revoked_at on public.webpilot_auth_realm_devices
for each row execute function public.fence_source_authority_on_membership_revoke();

-- Legacy snapshot path remains byte-compatible for legacy devices, but cannot bypass
-- the managed source authority once a device is explicitly activated.
create or replace function public.accept_device_snapshot(
    p_device_id text,
    p_snapshot jsonb,
    p_snapshot_schema_version integer,
    p_boot_id uuid,
    p_sequence bigint,
    p_generated_at timestamptz
)
returns table (
    status text,
    received_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    current_boot_id uuid;
    current_sequence bigint;
    current_snapshot jsonb;
    current_received_at timestamptz;
    accepted_at timestamptz;
    v_mode text;
begin
    select d.boot_id, d.sequence, d.snapshot, d.received_at
    into current_boot_id, current_sequence, current_snapshot, current_received_at
    from public.devices d
    where d.device_id = p_device_id
    for update;

    if not found then
        return query select 'device_not_found'::text, null::timestamptz;
        return;
    end if;

    select a.mode into v_mode
    from public.device_source_authority a
    where a.device_id = p_device_id
    for update;

    if v_mode = 'managed' then
        raise exception 'managed_snapshot_required';
    end if;

    if current_boot_id = p_boot_id then
        if current_sequence is not null and p_sequence < current_sequence then
            return query select 'out_of_order'::text, current_received_at;
            return;
        end if;
        if current_sequence = p_sequence then
            if current_snapshot = p_snapshot then
                return query select 'idempotent'::text, current_received_at;
                return;
            end if;
            return query select 'sequence_reuse_mismatch'::text, current_received_at;
            return;
        end if;
    end if;

    accepted_at := clock_timestamp();
    update public.devices d
    set snapshot = p_snapshot,
        snapshot_schema_version = p_snapshot_schema_version,
        boot_id = p_boot_id,
        sequence = p_sequence,
        generated_at = p_generated_at,
        received_at = accepted_at,
        updated_at = accepted_at
    where d.device_id = p_device_id;

    return query select 'accepted'::text, accepted_at;
end;
$$;

revoke all on function public.managed_snapshot_generated_at_matches(jsonb, timestamptz)
    from public, anon, authenticated;
revoke all on function public.ensure_device_source_authority_row()
    from public, anon, authenticated;
revoke all on function public.get_device_source_authority(text)
    from public, anon, authenticated;
revoke all on function public.bootstrap_managed_source_authority(text)
    from public, anon, authenticated;
revoke all on function public.accept_managed_snapshot_current_grant(
    text, text, bigint, uuid, uuid, jsonb, integer, uuid, bigint, timestamptz
) from public, anon, authenticated;
revoke all on function public.accept_managed_snapshot_transition_candidate(
    text, text, uuid, jsonb, integer, uuid, bigint, timestamptz
) from public, anon, authenticated;
revoke all on function public.return_source_authority_to_legacy(text)
    from public, anon, authenticated;
revoke all on function public.fence_source_authority_on_device_disable()
    from public, anon, authenticated;
revoke all on function public.fence_source_authority_on_binding_revoke()
    from public, anon, authenticated;
revoke all on function public.fence_source_authority_on_realm_deactivate()
    from public, anon, authenticated;
revoke all on function public.fence_source_authority_on_membership_revoke()
    from public, anon, authenticated;

grant execute on function public.get_device_source_authority(text)
    to service_role;
grant execute on function public.bootstrap_managed_source_authority(text)
    to service_role;
grant execute on function public.accept_managed_snapshot_current_grant(
    text, text, bigint, uuid, uuid, jsonb, integer, uuid, bigint, timestamptz
) to service_role;
grant execute on function public.accept_managed_snapshot_transition_candidate(
    text, text, uuid, jsonb, integer, uuid, bigint, timestamptz
) to service_role;
grant execute on function public.return_source_authority_to_legacy(text)
    to service_role;

-- C3-C: deterministic policy over persisted, server-timestamped state.
-- Caller must already hold the device transaction lock for any authority mutation.
-- This function never creates a grant; a transition RPC rechecks it under locks.
create or replace function public.source_candidate_reason(
    p_device_id text,
    p_source text,
    p_instance_id uuid,
    p_now timestamptz
)
returns text
language plpgsql
volatile
security definer
set search_path = pg_catalog, public
as $$
declare
    v_authority public.device_source_authority%rowtype;
    v_candidate public.device_source_heartbeats%rowtype;
    v_holder_hb public.device_source_heartbeats%rowtype;
    v_candidate_fresh boolean;
    v_auth_ready boolean := false;
    v_restart_threshold interval;
begin
    select a.* into v_authority
    from public.device_source_authority a
    where a.device_id=p_device_id;
    if v_authority.device_id is null or v_authority.mode <> 'managed' then
        return 'legacy_mode';
    end if;

    if not exists (
        select 1 from public.devices d
        where d.device_id=p_device_id and d.enabled=true
    ) then
        return 'device_disabled';
    end if;

    select h.* into v_candidate
    from public.device_source_heartbeats h
    where h.device_id=p_device_id and h.source=p_source
      and h.instance_id=p_instance_id;
    if v_candidate.device_id is null
       or v_candidate.instance_id is distinct from p_instance_id
       or v_candidate.process_healthy is not true
       or v_candidate.collection_healthy is not true then
        return case when p_source='cloud'
            then 'cloud_standby_stale' else 'failback_wait_stable' end;
    end if;

    v_candidate_fresh := case when p_source='desktop'
        then v_candidate.last_heartbeat_at > p_now - interval '90 seconds'
        else v_candidate.last_heartbeat_at > p_now - interval '60 seconds'
    end;
    if not v_candidate_fresh then
        return case when p_source='cloud'
            then 'cloud_standby_stale' else 'failback_wait_stable' end;
    end if;

    if p_source='cloud' then
        if v_candidate.persistent_state_ready is not true then
            return 'cloud_persistent_state_unavailable';
        end if;
        if v_candidate.last_candidate_generated_at is null
           or v_candidate.last_candidate_generated_at < p_now - interval '90 seconds'
           or v_candidate.last_candidate_generated_at > p_now + interval '60 seconds' then
            return 'cloud_standby_stale';
        end if;

        select exists (
            select 1
            from public.cloud_bindings b
            join public.webpilot_auth_realms r on r.realm_id=b.realm_id
            join public.webpilot_auth_realm_devices m
                on m.realm_id=b.realm_id and m.device_id=b.device_id
            where b.device_id=p_device_id and b.status='active'
              and r.active=true and m.revoked_at is null
              and exists (
                  select 1 from public.get_current_session_lease(b.realm_id, p_now) l
              )
        ) into v_auth_ready;
        if not v_auth_ready then
            return 'cloud_auth_unavailable';
        end if;
    end if;

    if v_authority.active_source=p_source then
        v_restart_threshold := case when p_source='desktop'
            then interval '90 seconds' else interval '60 seconds' end;
        -- Holder activity is independently persisted: candidate heartbeats
        -- can never substitute for the holder's own liveness.
        select h.* into v_holder_hb
        from public.device_source_heartbeats h
        where h.device_id=p_device_id
          and h.source=v_authority.active_source
          and h.instance_id=v_authority.holder_instance_id;
        if p_instance_id is distinct from v_authority.holder_instance_id
           and v_holder_hb.device_id is not null
           and v_authority.last_authoritative_snapshot_at is not null
           and greatest(
               v_holder_hb.last_heartbeat_at,
               v_authority.last_authoritative_snapshot_at
           ) <= p_now - v_restart_threshold then
            return case when p_source='desktop' then 'desktop_reacquire_granted'
                        else 'cloud_reacquire_granted' end;
        end if;
        return 'authority_fenced';
    end if;

    if v_authority.active_source='desktop' and p_source='cloud' then
        select h.* into v_holder_hb
        from public.device_source_heartbeats h
        where h.device_id=p_device_id and h.source='desktop'
          and h.instance_id=v_authority.holder_instance_id;
        if (
            (v_holder_hb.device_id is not null
             and v_holder_hb.last_heartbeat_at <= p_now - interval '180 seconds')
            or (v_authority.last_authoritative_snapshot_at is not null
                and v_authority.last_authoritative_snapshot_at <= p_now - interval '180 seconds')
        ) then
            return 'failover_granted';
        end if;
        return 'failover_wait_hysteresis';
    end if;

    if v_authority.active_source='cloud' and p_source='desktop' then
        if v_candidate.consecutive_healthy >= 3
           and v_candidate.healthy_since <= p_now - interval '120 seconds'
           and v_authority.granted_at <= p_now - interval '120 seconds' then
            return 'failback_granted';
        end if;
        return 'failback_wait_stable';
    end if;
    return 'authority_fenced';
end;
$$;

-- C3-C: one atomic server-owned heartbeat + optional current-holder renewal.
-- The caller is authenticated at the API boundary; Cloud binding identity is
-- also checked under transaction lock before any state is updated.
create or replace function public.record_source_heartbeat(
    p_device_id text,
    p_source text,
    p_instance_id uuid,
    p_process_healthy boolean,
    p_collection_healthy boolean,
    p_last_reported_generated_at timestamptz,
    p_last_candidate_generated_at timestamptz,
    p_persistent_state_ready boolean,
    p_cloud_binding_id uuid default null
)
returns table(
    status text,
    reason_code text,
    authority_epoch bigint,
    authority_lease_id uuid,
    holder_instance_id uuid,
    lease_expires_at timestamptz,
    renewed boolean
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    v_device public.devices%rowtype;
    v_authority public.device_source_authority%rowtype;
    v_heartbeat public.device_source_heartbeats%rowtype;
    v_holder_hb public.device_source_heartbeats%rowtype;
    v_locked_hb public.device_source_heartbeats%rowtype;
    v_pre_authority public.device_source_authority%rowtype;
    v_binding public.cloud_bindings%rowtype;
    v_realm public.webpilot_auth_realms%rowtype;
    v_membership public.webpilot_auth_realm_devices%rowtype;
    v_now timestamptz;
    v_healthy boolean;
    v_reason text;
    v_snapshot_fresh boolean;
    v_cloud_auth_ready boolean := false;
    v_is_holder boolean := false;
    v_renewed boolean := false;
    v_restart_threshold interval;
    v_snapshot_threshold interval;
begin
    if p_source not in ('desktop','cloud')
       or p_instance_id is null
       or p_process_healthy is null
       or p_collection_healthy is null
       or (p_source='desktop'
           and (p_persistent_state_ready is not null or p_cloud_binding_id is not null))
       or (p_source='cloud' and p_cloud_binding_id is null) then
        return query select 'rejected'::text,'snapshot_invalid'::text,
           null::bigint,null::uuid,null::uuid,null::timestamptz,false;
        return;
    end if;

    select d.* into v_device from public.devices d
    where d.device_id=p_device_id for update;
    if v_device.device_id is null or v_device.enabled is not true then
        return query select 'ineligible'::text,'device_disabled'::text,
           null::bigint,null::uuid,null::uuid,null::timestamptz,false;
        return;
    end if;

    if p_source='cloud' then
        select b.* into v_binding from public.cloud_bindings b
        where b.cloud_binding_id=p_cloud_binding_id and b.device_id=p_device_id
        for update;
        if v_binding.cloud_binding_id is null or v_binding.status <> 'active' then
            return query select 'ineligible'::text,'cloud_binding_unusable'::text,
                null::bigint,null::uuid,null::uuid,null::timestamptz,false;
            return;
        end if;
        select r.* into v_realm from public.webpilot_auth_realms r
        where r.realm_id=v_binding.realm_id for update;
        select m.* into v_membership from public.webpilot_auth_realm_devices m
        where m.realm_id=v_binding.realm_id and m.device_id=p_device_id for update;
        if v_realm.realm_id is null or v_realm.active is not true
           or v_membership.device_id is null or v_membership.revoked_at is not null then
            return query select 'ineligible'::text,'cloud_binding_unusable'::text,
                null::bigint,null::uuid,null::uuid,null::timestamptz,false;
            return;
        end if;
    end if;

    -- Discover keys under the device lock; this pre-read never authorizes a grant.
    select a.* into v_pre_authority from public.device_source_authority a
    where a.device_id=p_device_id;
    if v_pre_authority.device_id is null then
        return query select 'ineligible'::text,'db_unavailable'::text,
            null::bigint,null::uuid,null::uuid,null::timestamptz,false;
        return;
    end if;
    -- Lock both identities in a deterministic order, before authority.
    -- Device row serializes concurrent INSERTs for the same device.
    for v_locked_hb in
        select h.* from public.device_source_heartbeats h
        where h.device_id=p_device_id and (
            (h.source=p_source and h.instance_id=p_instance_id)
            or (h.source=v_pre_authority.active_source
                and h.instance_id=v_pre_authority.holder_instance_id)
        )
        order by h.source asc,h.instance_id asc for update
    loop
        if v_locked_hb.source=p_source and v_locked_hb.instance_id=p_instance_id then
            v_heartbeat := v_locked_hb;
        end if;
        if v_locked_hb.source=v_pre_authority.active_source
           and v_locked_hb.instance_id=v_pre_authority.holder_instance_id then
            v_holder_hb := v_locked_hb;
        end if;
    end loop;

    select a.* into v_authority from public.device_source_authority a
    where a.device_id=p_device_id for update;
    if v_authority.device_id is null
       or v_authority.mode is distinct from v_pre_authority.mode
       or v_authority.active_source is distinct from v_pre_authority.active_source
       or v_authority.holder_instance_id is distinct from v_pre_authority.holder_instance_id
       or v_authority.authority_epoch is distinct from v_pre_authority.authority_epoch
       or v_authority.authority_lease_id is distinct from v_pre_authority.authority_lease_id
       or v_authority.updated_at is distinct from v_pre_authority.updated_at then
        return query select 'ineligible'::text,'authority_fenced'::text,
            null::bigint,null::uuid,null::uuid,null::timestamptz,false;
        return;
    end if;

    v_now := clock_timestamp();
    v_restart_threshold := case when p_source='desktop'
        then interval '90 seconds' else interval '60 seconds' end;
    v_snapshot_threshold := case when v_authority.active_source='desktop'
        then interval '120 seconds' else interval '90 seconds' end;
    v_healthy := p_process_healthy and p_collection_healthy;
    v_is_holder := (
        v_authority.mode='managed'
        and v_authority.active_source=p_source
        and v_authority.holder_instance_id=p_instance_id
    );

    insert into public.device_source_heartbeats(
        device_id,source,instance_id,last_heartbeat_at,process_healthy,
        collection_healthy,healthy_since,consecutive_healthy,last_collection_ok_at,
        last_reported_generated_at,last_candidate_generated_at,last_reason_code,
        persistent_state_ready,updated_at
    ) values (
        p_device_id,p_source,p_instance_id,v_now,p_process_healthy,
        p_collection_healthy,case when v_healthy then v_now else null end,
        case when v_healthy then 1 else 0 end,
        case when v_healthy then v_now else null end,
        p_last_reported_generated_at,p_last_candidate_generated_at,
        null,
        case when p_source='cloud' then p_persistent_state_ready else null end,
        v_now
    ) on conflict (device_id,source,instance_id) do update
    set last_heartbeat_at=v_now,
        process_healthy=p_process_healthy,
        collection_healthy=p_collection_healthy,
        healthy_since=case
            when v_healthy
                 and v_heartbeat.instance_id=p_instance_id
                 and v_heartbeat.process_healthy
                 and v_heartbeat.collection_healthy
                 and v_heartbeat.last_heartbeat_at > v_now - v_restart_threshold
            then v_heartbeat.healthy_since
            when v_healthy then v_now else null end,
        consecutive_healthy=case
            when v_healthy
                 and v_heartbeat.instance_id=p_instance_id
                 and v_heartbeat.process_healthy
                 and v_heartbeat.collection_healthy
                 and v_heartbeat.last_heartbeat_at > v_now - v_restart_threshold
            then v_heartbeat.consecutive_healthy+1
            when v_healthy then 1 else 0 end,
        last_collection_ok_at=case when v_healthy then v_now
            else v_heartbeat.last_collection_ok_at end,
        last_reported_generated_at=p_last_reported_generated_at,
        last_candidate_generated_at=p_last_candidate_generated_at,
        last_reason_code=null,
        persistent_state_ready=case when p_source='cloud'
            then p_persistent_state_ready else null end,
        updated_at=v_now;

    -- Stale marker is anchored to the REAL threshold, not the time this
    -- request happens to notice it, and survives API restart.
    if v_authority.mode='managed' and
       v_authority.last_authoritative_snapshot_at is not null
       and v_authority.last_authoritative_snapshot_at <= v_now - v_snapshot_threshold then
        update public.device_source_authority a
        set authoritative_snapshot_stale_since =
          v_authority.last_authoritative_snapshot_at
              + case when v_authority.active_source='desktop'
                     then interval '120 seconds' else interval '90 seconds' end
        where a.device_id=p_device_id
          and a.authoritative_snapshot_stale_since is null;
    end if;

    if p_source='cloud' then
        select exists (
            select 1 from public.get_current_session_lease(v_binding.realm_id,v_now) l
        ) into v_cloud_auth_ready;
    end if;

    v_snapshot_fresh := (
        v_authority.last_authoritative_snapshot_at is not null
        and v_authority.last_authoritative_snapshot_at > v_now
            - case when p_source='desktop'
                   then interval '120 seconds' else interval '90 seconds' end
    );

    if v_is_holder then
        if v_authority.lease_expires_at <= v_now then
            v_reason := 'authority_lease_expired';
        elsif not v_healthy then
            v_reason := case when p_source='desktop'
                then 'desktop_degraded' else 'cloud_standby_stale' end;
        elsif p_source='cloud' and p_persistent_state_ready is not true then
            v_reason := 'cloud_persistent_state_unavailable';
        elsif p_source='cloud' and (
            v_authority.cloud_binding_id is distinct from p_cloud_binding_id
            or not v_cloud_auth_ready
        ) then
            v_reason := 'cloud_auth_unavailable';
        elsif not v_snapshot_fresh then
            v_reason := case when p_source='desktop'
                then 'desktop_snapshot_stale' else 'cloud_snapshot_stale' end;
        else
            update public.device_source_authority a
            set lease_expires_at=v_now+interval '180 seconds',
                last_renewed_at=v_now,
                updated_at=v_now
            where a.device_id=p_device_id;
            v_renewed := true;
            v_reason := case when p_source='desktop' then 'desktop_healthy' else null end;
        end if;
    else
        v_reason := public.source_candidate_reason(
            p_device_id,p_source,p_instance_id,v_now
        );

    end if;

    -- Diagnostic reason belongs exclusively to the reporting instance.
    update public.device_source_heartbeats h
    set last_reason_code=v_reason
    where h.device_id=p_device_id and h.source=p_source
      and h.instance_id=p_instance_id;

    -- Only the authenticated CURRENT holder can receive its actual grant.
    -- Non-holders never get future authority credentials.
    if v_is_holder and v_authority.lease_expires_at > v_now then
        return query select 'accepted'::text,v_reason,
            v_authority.authority_epoch,v_authority.authority_lease_id,
            v_authority.holder_instance_id,
            case when v_renewed then v_now+interval '180 seconds'
                 else v_authority.lease_expires_at end,v_renewed;
        return;
    end if;
    return query select 'accepted'::text,v_reason,
        null::bigint,null::uuid,null::uuid,null::timestamptz,false;
end;
$$;

revoke all on function public.source_candidate_reason(text,text,uuid,timestamptz)
    from public, anon, authenticated;
revoke all on function public.record_source_heartbeat(
    text,text,uuid,boolean,boolean,timestamptz,timestamptz,boolean,uuid
) from public, anon, authenticated;
grant execute on function public.record_source_heartbeat(
    text,text,uuid,boolean,boolean,timestamptz,timestamptz,boolean,uuid
) to service_role;
