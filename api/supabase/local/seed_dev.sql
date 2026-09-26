insert into public.devices (
    device_id,
    device_secret_hash,
    view_secret_hash,
    view_secret_updated_at,
    updated_at
)
values (
    'pecem-01',
    '21a05e78e14ce064d997bdb545c6816d0a37427ba38fd2a4cebf604242aa38c0',
    '4b4f9630c1c4baeba6903a09b74e389d2c6f79e8dc566e3e07af35465ff7709e',
    now(),
    now()
)
on conflict (device_id) do update
set
    device_secret_hash = excluded.device_secret_hash,
    view_secret_hash = excluded.view_secret_hash,
    view_secret_updated_at = now(),
    updated_at = now();
