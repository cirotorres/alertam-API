-- Migration 016: temporary six-digit mobile pairing codes.

create table if not exists public.mobile_pairing_codes (
    device_id text primary key references public.devices(device_id) on delete cascade,
    code_hash text not null unique,
    expires_at timestamptz not null,
    redeemed_at timestamptz,
    ticket_hash text,
    ticket_expires_at timestamptz,
    consumed_at timestamptz,
    consumed_for text,
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    constraint mobile_pairing_codes_hash_check
        check (char_length(code_hash) = 64),
    constraint mobile_pairing_ticket_hash_check
        check (ticket_hash is null or char_length(ticket_hash) = 64)
);

create table if not exists public.mobile_pairing_redeem_windows (
    window_start timestamptz primary key,
    failures integer not null default 0,
    constraint mobile_pairing_redeem_failures_check check (failures >= 0)
);

alter table public.mobile_pairing_codes enable row level security;
alter table public.mobile_pairing_redeem_windows enable row level security;
revoke all on table public.mobile_pairing_codes from anon, authenticated;
revoke all on table public.mobile_pairing_redeem_windows from anon, authenticated;

create or replace function public.replace_mobile_pairing_code(
    p_device_id text,
    p_code_hash text,
    p_expires_at timestamptz
)
returns table (updated boolean)
language plpgsql
security definer
set search_path = public
as $$
begin
    if not exists (
        select 1 from public.devices d where d.device_id = p_device_id
    ) then
        return query select false;
        return;
    end if;

    insert into public.mobile_pairing_codes (
        device_id,
        code_hash,
        expires_at,
        redeemed_at,
        ticket_hash,
        ticket_expires_at,
        consumed_at,
        consumed_for,
        created_at,
        updated_at
    )
    values (
        p_device_id,
        p_code_hash,
        p_expires_at,
        null,
        null,
        null,
        null,
        null,
        clock_timestamp(),
        clock_timestamp()
    )
    on conflict (device_id) do update
    set
        code_hash = excluded.code_hash,
        expires_at = excluded.expires_at,
        redeemed_at = null,
        ticket_hash = null,
        ticket_expires_at = null,
        consumed_at = null,
        consumed_for = null,
        created_at = clock_timestamp(),
        updated_at = clock_timestamp();

    return query select true;
end;
$$;

create or replace function public.redeem_mobile_pairing_code(
    p_code_hash text,
    p_ticket_hash text,
    p_ticket_expires_at timestamptz,
    p_now timestamptz
)
returns table (
    status text,
    device_id text,
    ticket_expires_at timestamptz
)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_window timestamptz := date_trunc('minute', p_now);
    v_failures integer;
    v_code public.mobile_pairing_codes%rowtype;
begin
    delete from public.mobile_pairing_redeem_windows
    where window_start < p_now - interval '1 day';

    insert into public.mobile_pairing_redeem_windows(window_start, failures)
    values (v_window, 0)
    on conflict (window_start) do nothing;

    select rw.failures
    into v_failures
    from public.mobile_pairing_redeem_windows rw
    where rw.window_start = v_window
    for update;

    if coalesce(v_failures, 0) >= 30 then
        return query select 'rate_limited'::text, null::text, null::timestamptz;
        return;
    end if;

    select *
    into v_code
    from public.mobile_pairing_codes pc
    where pc.code_hash = p_code_hash
    for update;

    if (
        not found
        or v_code.redeemed_at is not null
        or v_code.expires_at <= p_now
    ) then
        update public.mobile_pairing_redeem_windows
        set failures = failures + 1
        where window_start = v_window;
        return query select 'invalid'::text, null::text, null::timestamptz;
        return;
    end if;

    update public.mobile_pairing_codes
    set
        redeemed_at = p_now,
        ticket_hash = p_ticket_hash,
        ticket_expires_at = p_ticket_expires_at,
        consumed_at = null,
        consumed_for = null,
        updated_at = p_now
    where mobile_pairing_codes.device_id = v_code.device_id;

    return query
    select 'ok'::text, v_code.device_id, p_ticket_expires_at;
end;
$$;

create or replace function public.validate_mobile_pairing_ticket(
    p_device_id text,
    p_ticket_hash text,
    p_now timestamptz
)
returns table (valid boolean)
language sql
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.mobile_pairing_codes pc
        where pc.device_id = p_device_id
          and pc.ticket_hash = p_ticket_hash
          and pc.redeemed_at is not null
          and pc.ticket_expires_at > p_now
    );
$$;

create or replace function public.consume_mobile_pairing_ticket(
    p_device_id text,
    p_ticket_hash text,
    p_purpose text,
    p_now timestamptz
)
returns table (valid boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_code public.mobile_pairing_codes%rowtype;
begin
    select *
    into v_code
    from public.mobile_pairing_codes pc
    where pc.device_id = p_device_id
      and pc.ticket_hash = p_ticket_hash
      and pc.redeemed_at is not null
      and pc.ticket_expires_at > p_now
    for update;

    if not found then
        return query select false;
        return;
    end if;

    if v_code.consumed_for is not null then
        return query select v_code.consumed_for = p_purpose;
        return;
    end if;

    update public.mobile_pairing_codes
    set
        consumed_at = p_now,
        consumed_for = p_purpose,
        updated_at = p_now
    where mobile_pairing_codes.device_id = p_device_id;

    return query select true;
end;
$$;

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

    if changed_rows = 1 then
        delete from public.mobile_pairing_codes
        where device_id = p_device_id;
    end if;

    return query
    select changed_rows = 1;
end;
$$;

revoke all on function public.replace_mobile_pairing_code(text, text, timestamptz)
    from public, anon, authenticated;
revoke all on function public.redeem_mobile_pairing_code(text, text, timestamptz, timestamptz)
    from public, anon, authenticated;
revoke all on function public.validate_mobile_pairing_ticket(text, text, timestamptz)
    from public, anon, authenticated;
revoke all on function public.consume_mobile_pairing_ticket(text, text, text, timestamptz)
    from public, anon, authenticated;

grant execute on function public.replace_mobile_pairing_code(text, text, timestamptz)
    to service_role;
grant execute on function public.redeem_mobile_pairing_code(text, text, timestamptz, timestamptz)
    to service_role;
grant execute on function public.validate_mobile_pairing_ticket(text, text, timestamptz)
    to service_role;
grant execute on function public.consume_mobile_pairing_ticket(text, text, text, timestamptz)
    to service_role;
