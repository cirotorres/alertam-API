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
set search_path = public
as $$
declare
    current_boot_id uuid;
    current_sequence bigint;
    current_snapshot jsonb;
    current_received_at timestamptz;
    accepted_at timestamptz;
begin
    select
        d.boot_id,
        d.sequence,
        d.snapshot,
        d.received_at
    into
        current_boot_id,
        current_sequence,
        current_snapshot,
        current_received_at
    from public.devices as d
    where d.device_id = p_device_id
    for update;

    if not found then
        return query
        select
            'device_not_found'::text,
            null::timestamptz;
        return;
    end if;

    if current_boot_id = p_boot_id then
        if current_sequence is not null
           and p_sequence < current_sequence then
            return query
            select
                'out_of_order'::text,
                current_received_at;
            return;
        end if;

        if current_sequence = p_sequence then
            if current_snapshot = p_snapshot then
                return query
                select
                    'idempotent'::text,
                    current_received_at;
                return;
            end if;

            return query
            select
                'sequence_reuse_mismatch'::text,
                current_received_at;
            return;
        end if;
    end if;

    accepted_at := clock_timestamp();

    update public.devices
    set
        snapshot = p_snapshot,
        snapshot_schema_version = p_snapshot_schema_version,
        boot_id = p_boot_id,
        sequence = p_sequence,
        generated_at = p_generated_at,
        received_at = accepted_at,
        updated_at = accepted_at
    where device_id = p_device_id;

    return query
    select
        'accepted'::text,
        accepted_at;
end;
$$;

revoke all on function public.accept_device_snapshot(
    text,
    jsonb,
    integer,
    uuid,
    bigint,
    timestamptz
) from public, anon, authenticated;

grant execute on function public.accept_device_snapshot(
    text,
    jsonb,
    integer,
    uuid,
    bigint,
    timestamptz
) to service_role;
