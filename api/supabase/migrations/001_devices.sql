create table if not exists public.devices (
    device_id text primary key,
    device_secret_hash text not null,
    view_secret_hash text null,
    snapshot jsonb null,
    snapshot_schema_version integer null,
    boot_id uuid null,
    sequence bigint null,
    generated_at timestamptz null,
    received_at timestamptz null,
    view_secret_updated_at timestamptz null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint devices_sequence_positive
        check (sequence is null or sequence > 0),
    constraint devices_snapshot_schema_positive
        check (
            snapshot_schema_version is null
            or snapshot_schema_version > 0
        )
);

alter table public.devices enable row level security;

revoke all on table public.devices from anon, authenticated;
