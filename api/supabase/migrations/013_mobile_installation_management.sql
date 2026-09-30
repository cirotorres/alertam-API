alter table public.mobile_installations
    add column if not exists platform text,
    add column if not exists display_code text;

update public.mobile_installations
set platform = 'other'
where platform is null or platform not in ('ios', 'android', 'other');

create or replace function public.random_mobile_display_code()
returns text
language plpgsql
set search_path = public
as $$
declare
    v_alphabet constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    v_code text := '';
    v_index integer;
begin
    for v_index in 1..6 loop
        v_code := v_code || substr(
            v_alphabet,
            1 + floor(random() * length(v_alphabet))::integer,
            1
        );
    end loop;
    return v_code;
end;
$$;

do $$
declare
    v_row record;
    v_code text;
begin
    for v_row in
        select installation_id
        from public.mobile_installations
        where display_code is null
        order by installation_id
    loop
        loop
            v_code := public.random_mobile_display_code();
            exit when not exists (
                select 1
                from public.mobile_installations mi
                where mi.display_code = v_code
            );
        end loop;

        update public.mobile_installations
        set display_code = v_code
        where installation_id = v_row.installation_id;
    end loop;
end;
$$;

alter table public.mobile_installations
    alter column platform set default 'other',
    alter column platform set not null,
    alter column display_code set not null;

alter table public.mobile_installations
    drop constraint if exists mobile_installations_platform_check,
    add constraint mobile_installations_platform_check
        check (platform in ('ios', 'android', 'other')),
    drop constraint if exists mobile_installations_display_code_check,
    add constraint mobile_installations_display_code_check
        check (display_code ~ '^[A-HJ-NP-Z2-9]{6}$');

create unique index if not exists mobile_installations_display_code_unique
    on public.mobile_installations (display_code);

create or replace function public.ensure_mobile_installation(
    p_device_id text,
    p_installation_id uuid,
    p_platform text,
    p_display_code text
)
returns setof public.mobile_installations
language plpgsql
security definer
set search_path = public
as $$
declare
    v_existing public.mobile_installations%rowtype;
    v_now timestamptz := clock_timestamp();
    v_platform text := case
        when lower(coalesce(p_platform, '')) in ('ios', 'android', 'other')
            then lower(p_platform)
        else 'other'
    end;
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

    if found and v_existing.active = false then
        return;
    end if;

    if not found then
        if p_display_code is null then
            return;
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
            p_installation_id,
            p_device_id,
            true,
            v_now,
            v_now,
            null,
            v_now,
            v_platform,
            p_display_code
        );
    else
        update public.mobile_installations
        set
            last_seen_at = v_now,
            updated_at = v_now,
            platform = case
                when platform = 'other' and v_platform <> 'other'
                    then v_platform
                else platform
            end
        where installation_id = p_installation_id;
    end if;

    return query
    select *
    from public.mobile_installations mi
    where mi.installation_id = p_installation_id
      and mi.device_id = p_device_id
      and mi.active = true;
end;
$$;

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
    v_code text;
begin
    if exists (
        select 1
        from public.mobile_installations mi
        where mi.installation_id = p_installation_id
    ) then
        return query
        select *
        from public.ensure_mobile_installation(
            p_device_id,
            p_installation_id,
            'other',
            'AAAAAA'
        );
        return;
    end if;

    loop
        v_code := public.random_mobile_display_code();
        begin
            return query
            select *
            from public.ensure_mobile_installation(
                p_device_id,
                p_installation_id,
                'other',
                v_code
            );
            return;
        exception when unique_violation then
            null;
        end;
    end loop;
end;
$$;

create or replace function public.touch_mobile_installation(
    p_device_id text,
    p_installation_id uuid,
    p_platform text
)
returns setof public.mobile_installations
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_platform text := case
        when lower(coalesce(p_platform, '')) in ('ios', 'android', 'other')
            then lower(p_platform)
        else 'other'
    end;
begin
    update public.mobile_installations
    set
        last_seen_at = v_now,
        updated_at = v_now,
        platform = case
            when platform = 'other' and v_platform <> 'other'
                then v_platform
            else platform
        end
    where installation_id = p_installation_id
      and device_id = p_device_id
      and active = true;

    return query
    select *
    from public.mobile_installations mi
    where mi.installation_id = p_installation_id
      and mi.device_id = p_device_id
      and mi.active = true;
end;
$$;

create or replace function public.list_mobile_installations(
    p_device_id text,
    p_revoked_since timestamptz
)
returns setof public.mobile_installations
language sql
security definer
set search_path = public
as $$
    select mi.*
    from public.mobile_installations mi
    where mi.device_id = p_device_id
      and (
          mi.active = true
          or mi.revoked_at >= p_revoked_since
      )
    order by mi.created_at, mi.installation_id;
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
    v_exists boolean;
    v_now timestamptz := clock_timestamp();
begin
    select exists (
        select 1
        from public.mobile_installations mi
        where mi.installation_id = p_installation_id
          and mi.device_id = p_device_id
    ) into v_exists;

    if not v_exists then
        return query select false;
        return;
    end if;

    update public.tracked_vessels
    set
        active = false,
        stopped_at = coalesce(stopped_at, v_now),
        updated_at = v_now
    where installation_id = p_installation_id
      and device_id = p_device_id
      and active = true;

    update public.push_installations
    set
        endpoint = null,
        p256dh = null,
        auth = null,
        active = false,
        last_seen_at = v_now,
        updated_at = v_now
    where installation_id = p_installation_id
      and device_id = p_device_id
      and active = true;

    update public.mobile_installations
    set
        active = false,
        last_seen_at = case when active then v_now else last_seen_at end,
        revoked_at = coalesce(revoked_at, v_now),
        updated_at = v_now
    where installation_id = p_installation_id
      and device_id = p_device_id;

    return query select true;
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
            last_seen_at = case when active then v_now else last_seen_at end,
            revoked_at = coalesce(revoked_at, v_now),
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
        where device_id = p_device_id
          and active = true;
    end if;

    return query select v_count = 1;
end;
$$;

revoke all on function public.ensure_mobile_installation(text, uuid, text, text)
    from public, anon, authenticated;
revoke all on function public.ensure_mobile_installation(text, uuid)
    from public, anon, authenticated;
revoke all on function public.touch_mobile_installation(text, uuid, text)
    from public, anon, authenticated;
revoke all on function public.list_mobile_installations(text, timestamptz)
    from public, anon, authenticated;
revoke all on function public.revoke_mobile_installation(text, uuid)
    from public, anon, authenticated;
revoke all on function public.rotate_device_view_secret(text, text)
    from public, anon, authenticated;

grant execute on function public.ensure_mobile_installation(text, uuid, text, text)
    to service_role;
grant execute on function public.ensure_mobile_installation(text, uuid)
    to service_role;
grant execute on function public.touch_mobile_installation(text, uuid, text)
    to service_role;
grant execute on function public.list_mobile_installations(text, timestamptz)
    to service_role;
grant execute on function public.revoke_mobile_installation(text, uuid)
    to service_role;
grant execute on function public.rotate_device_view_secret(text, text)
    to service_role;
