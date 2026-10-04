alter table public.push_installations
    add column if not exists pref_anchored boolean not null default true;

create or replace function public.update_push_preferences(
    p_device_id text,
    p_installation_id uuid,
    p_confirmed boolean,
    p_updated boolean,
    p_completed boolean,
    p_cancelled boolean,
    p_anchored boolean
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
        pref_anchored = p_anchored,
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

revoke all on function public.update_push_preferences(
    text,
    uuid,
    boolean,
    boolean,
    boolean,
    boolean,
    boolean
) from public, anon, authenticated;

grant execute on function public.update_push_preferences(
    text,
    uuid,
    boolean,
    boolean,
    boolean,
    boolean,
    boolean
) to service_role;
