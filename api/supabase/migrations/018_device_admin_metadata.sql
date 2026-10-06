alter table public.devices
    add column if not exists description text null;

alter table public.devices
    add column if not exists enabled boolean not null default true;
