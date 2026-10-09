#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
do $$
begin
    create role anon noinherit;
exception when duplicate_object then null;
end $$;

do $$
begin
    create role authenticated noinherit;
exception when duplicate_object then null;
end $$;

do $$
begin
    create role service_role noinherit bypassrls;
exception when duplicate_object then null;
end $$;
SQL

for name in     001_devices.sql     018_device_admin_metadata.sql     019_cloud_binding_realm.sql     020_webpilot_session_broker.sql
do
    echo "sandbox migration: $name"
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "/migrations/$name"
done
