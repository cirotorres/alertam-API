create table if not exists public.mobile_session_switches (
    switch_id uuid primary key,
    from_device_id text not null references public.devices(device_id)
        on delete cascade,
    from_installation_id uuid not null
        references public.mobile_installations(installation_id)
        on delete cascade,
    to_device_id text not null references public.devices(device_id)
        on delete cascade,
    to_installation_id uuid not null
        references public.mobile_installations(installation_id)
        on delete cascade,
    platform text not null,
    display_code text not null,
    completed_at timestamptz not null default clock_timestamp(),
    constraint mobile_session_switches_platform_check
        check (platform in ('ios', 'android', 'other'))
);

create unique index if not exists mobile_session_switches_target_idx
    on public.mobile_session_switches (to_installation_id);

alter table public.mobile_session_switches enable row level security;
revoke all on table public.mobile_session_switches
    from anon, authenticated;

create or replace function public.switch_mobile_installation(
    p_switch_id uuid,
    p_from_device_id text,
    p_from_installation_id uuid,
    p_to_device_id text,
    p_to_installation_id uuid,
    p_platform text,
    p_display_code text
)
returns setof public.mobile_installations
language plpgsql
security definer
set search_path = public
as $$
declare
    v_previous public.mobile_session_switches%rowtype;
    v_source public.mobile_installations%rowtype;
    v_now timestamptz := clock_timestamp();
    v_platform text := case
        when lower(coalesce(p_platform, '')) in ('ios', 'android', 'other')
            then lower(p_platform)
        else 'other'
    end;
begin
    select *
    into v_previous
    from public.mobile_session_switches ms
    where ms.switch_id = p_switch_id
    for update;

    if found then
        if (
            v_previous.from_device_id <> p_from_device_id
            or v_previous.from_installation_id <> p_from_installation_id
            or v_previous.to_device_id <> p_to_device_id
            or v_previous.to_installation_id <> p_to_installation_id
            or v_previous.platform <> v_platform
        ) then
            raise exception 'mobile_session_switch_conflict'
                using errcode = 'P0001';
        end if;

        return query
        select mi.*
        from public.mobile_installations mi
        where mi.installation_id = v_previous.to_installation_id
          and mi.device_id = v_previous.to_device_id;
        return;
    end if;

    if p_from_device_id = p_to_device_id then
        raise exception 'mobile_session_switch_conflict'
            using errcode = 'P0001';
    end if;

    select *
    into v_source
    from public.mobile_installations mi
    where mi.installation_id = p_from_installation_id
      and mi.device_id = p_from_device_id
    for update;

    if not found or v_source.active = false then
        return;
    end if;

    if not exists (
        select 1
        from public.devices d
        where d.device_id = p_to_device_id
    ) then
        return;
    end if;

    if exists (
        select 1
        from public.mobile_installations mi
        where mi.installation_id = p_to_installation_id
    ) then
        raise exception 'mobile_session_switch_conflict'
            using errcode = 'P0001';
    end if;

    insert into public.mobile_installations (
        installation_id,
        device_id,
        active,
        created_at,
        last_seen_at,
        revoked_at,
        updated_at,
        platform,
        display_code
    )
    values (
        p_to_installation_id,
        p_to_device_id,
        true,
        v_now,
        v_now,
        null,
        v_now,
        v_platform,
        p_display_code
    );

    update public.tracked_vessels
    set
        active = false,
        stopped_at = coalesce(stopped_at, v_now),
        updated_at = v_now
    where installation_id = p_from_installation_id
      and device_id = p_from_device_id
      and active = true;

    update public.push_installations
    set
        endpoint = null,
        p256dh = null,
        auth = null,
        active = false,
        last_seen_at = v_now,
        updated_at = v_now
    where installation_id = p_from_installation_id
      and device_id = p_from_device_id
      and active = true;

    update public.mobile_installations
    set
        active = false,
        last_seen_at = v_now,
        revoked_at = coalesce(revoked_at, v_now),
        updated_at = v_now
    where installation_id = p_from_installation_id
      and device_id = p_from_device_id
      and active = true;

    insert into public.mobile_session_switches (
        switch_id,
        from_device_id,
        from_installation_id,
        to_device_id,
        to_installation_id,
        platform,
        display_code,
        completed_at
    )
    values (
        p_switch_id,
        p_from_device_id,
        p_from_installation_id,
        p_to_device_id,
        p_to_installation_id,
        v_platform,
        p_display_code,
        v_now
    );

    return query
    select mi.*
    from public.mobile_installations mi
    where mi.installation_id = p_to_installation_id
      and mi.device_id = p_to_device_id;
end;
$$;

revoke all on function public.switch_mobile_installation(
    uuid, text, uuid, text, uuid, text, text
) from public, anon, authenticated;

grant execute on function public.switch_mobile_installation(
    uuid, text, uuid, text, uuid, text, text
) to service_role;
