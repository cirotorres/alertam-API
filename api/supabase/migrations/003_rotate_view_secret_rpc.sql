create or replace function public.rotate_device_view_secret(
    p_device_id text,
    p_view_secret_hash text
)
returns table (
    updated boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
    changed_at timestamptz;
    changed_rows integer;
begin
    changed_at := clock_timestamp();

    update public.devices
    set
        view_secret_hash = p_view_secret_hash,
        view_secret_updated_at = changed_at,
        updated_at = changed_at
    where device_id = p_device_id;

    get diagnostics changed_rows = row_count;

    return query
    select changed_rows = 1;
end;
$$;

revoke all on function public.rotate_device_view_secret(
    text,
    text
) from public, anon, authenticated;

grant execute on function public.rotate_device_view_secret(
    text,
    text
) to service_role;
