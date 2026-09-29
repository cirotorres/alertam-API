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


create or replace function public.project_tracked_vessels(
    p_device_id text,
    p_vessel_identity text,
    p_vessel_imo text,
    p_vessel_name text,
    p_observed_at timestamptz,
    p_replace_current boolean,
    p_current jsonb,
    p_patch jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer;
    v_name text := regexp_replace(
        upper(trim(p_vessel_name)),
        '[[:space:]]+',
        ' ',
        'g'
    );
    v_empty_current jsonb := '{
        "present": null,
        "status": null,
        "section": null,
        "berth": null,
        "side": null,
        "eta": null,
        "etb_ets": null,
        "pob": null,
        "pob_at": null
    }'::jsonb;
begin
    update public.tracked_vessels tv
    set
        vessel_identity = case
            when p_vessel_imo is not null then p_vessel_identity
            else tv.vessel_identity
        end,
        vessel_imo = coalesce(p_vessel_imo, tv.vessel_imo),
        vessel_name = case
            when p_vessel_imo is not null then p_vessel_name
            else tv.vessel_name
        end,
        current = case
            when p_replace_current then p_current
            else coalesce(tv.current, v_empty_current) || coalesce(p_patch, '{}'::jsonb)
        end,
        last_seen_at = p_observed_at,
        updated_at = clock_timestamp()
    where tv.device_id = p_device_id
      and tv.active = true
      and (tv.last_seen_at is null or p_observed_at >= tv.last_seen_at)
      and (
          tv.vessel_identity = p_vessel_identity
          or (
              p_vessel_imo is not null
              and tv.vessel_imo = p_vessel_imo
          )
          or (
              p_vessel_imo is not null
              and tv.vessel_imo is null
              and regexp_replace(
                      upper(trim(tv.vessel_name)),
                      '[[:space:]]+',
                      ' ',
                      'g'
                  ) = v_name
          )
          or (
              p_vessel_imo is null
              and tv.vessel_imo is null
              and regexp_replace(
                      upper(trim(tv.vessel_name)),
                      '[[:space:]]+',
                      ' ',
                      'g'
                  ) = v_name
          )
      );

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;

create or replace function public.list_tracked_vessel_timeline(
    p_device_id text,
    p_installation_id uuid,
    p_tracked_vessel_id uuid
)
returns table (
    kind text,
    ingestion_id bigint,
    ingested_at timestamptz,
    event_payload jsonb
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_tracked public.tracked_vessels%rowtype;
    v_name text;
begin
    select *
    into v_tracked
    from public.tracked_vessels tv
    where tv.tracked_vessel_id = p_tracked_vessel_id
      and tv.device_id = p_device_id
      and tv.installation_id = p_installation_id;

    if not found then
        return;
    end if;

    v_name := regexp_replace(
        upper(trim(v_tracked.vessel_name)),
        '[[:space:]]+',
        ' ',
        'g'
    );

    return query
    select q.kind, q.ingestion_id, q.ingested_at, q.event_payload
    from (
        select
            'MANEUVER'::text as kind,
            me.ingestion_id,
            me.ingested_at,
            me.event_payload
        from public.maneuver_events me
        where me.device_id = p_device_id
          and (
              me.event_payload->>'vessel_identity' = v_tracked.vessel_identity
              or (
                  v_tracked.vessel_imo is not null
                  and me.event_payload->>'vessel_imo' = v_tracked.vessel_imo
              )
              or (
                  me.event_payload->>'vessel_imo' is null
                  and regexp_replace(
                          upper(trim(me.event_payload->>'vessel_name')),
                          '[[:space:]]+',
                          ' ',
                          'g'
                      ) = v_name
              )
          )

        union all

        select
            'TRACKING'::text as kind,
            vte.ingestion_id,
            vte.ingested_at,
            vte.event_payload
        from public.vessel_tracking_events vte
        where vte.device_id = p_device_id
          and (
              vte.vessel_identity = v_tracked.vessel_identity
              or (
                  v_tracked.vessel_imo is not null
                  and vte.vessel_imo = v_tracked.vessel_imo
              )
              or (
                  vte.vessel_imo is null
                  and regexp_replace(
                          upper(trim(vte.vessel_name)),
                          '[[:space:]]+',
                          ' ',
                          'g'
                      ) = v_name
              )
          )
    ) q
    order by
        (q.event_payload->>'occurred_at')::timestamptz asc,
        q.ingested_at asc,
        (q.event_payload->>'event_id')::uuid asc;
end;
$$;

create or replace function public.list_installation_tracking_events(
    p_device_id text,
    p_installation_id uuid,
    p_after bigint,
    p_limit integer
)
returns table (
    tracked_vessel_id uuid,
    ingestion_id bigint,
    ingested_at timestamptz,
    event_payload jsonb
)
language sql
security definer
set search_path = public
as $$
    select
        tv.tracked_vessel_id,
        vte.ingestion_id,
        vte.ingested_at,
        vte.event_payload
    from public.vessel_tracking_events vte
    join public.tracked_vessels tv
      on tv.device_id = vte.device_id
     and tv.installation_id = p_installation_id
     and tv.active = true
     and (
         tv.vessel_identity = vte.vessel_identity
         or (
             vte.vessel_imo is not null
             and tv.vessel_imo = vte.vessel_imo
         )
         or (
             vte.vessel_imo is not null
             and tv.vessel_imo is null
             and regexp_replace(
                     upper(trim(tv.vessel_name)),
                     '[[:space:]]+',
                     ' ',
                     'g'
                 ) = regexp_replace(
                     upper(trim(vte.vessel_name)),
                     '[[:space:]]+',
                     ' ',
                     'g'
                 )
         )
     )
    where vte.device_id = p_device_id
      and vte.ingestion_id > p_after
      and vte.occurred_at >= tv.started_at
    order by vte.ingestion_id asc
    limit p_limit;
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

revoke all on function public.project_tracked_vessels(
    text, text, text, text, timestamptz, boolean, jsonb, jsonb
) from public, anon, authenticated;
revoke all on function public.list_tracked_vessel_timeline(text, uuid, uuid)
    from public, anon, authenticated;
revoke all on function public.list_installation_tracking_events(
    text, uuid, bigint, integer
) from public, anon, authenticated;

grant execute on function public.project_tracked_vessels(
    text, text, text, text, timestamptz, boolean, jsonb, jsonb
) to service_role;
grant execute on function public.list_tracked_vessel_timeline(text, uuid, uuid)
    to service_role;
grant execute on function public.list_installation_tracking_events(
    text, uuid, bigint, integer
) to service_role;
