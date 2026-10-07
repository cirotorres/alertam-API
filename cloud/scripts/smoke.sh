#!/usr/bin/env bash
set -euo pipefail

IMAGE="${CLOUD_IMAGE:-alertam-cloud-infra-spike:local}"
NAME="${CLOUD_CONTAINER_NAME:-alertam-cloud-infra-spike-smoke}"
SENTINEL="spike-sentinel-not-for-logs"

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup

docker run -d \
  --name "$NAME" \
  -p 127.0.0.1::8080 \
  -e PORT=8080 \
  -e SPIKE_TEST_SECRET="$SENTINEL" \
  "$IMAGE" >/dev/null

HOST_PORT="$(docker port "$NAME" 8080/tcp | sed -n 's/.*://p' | head -n 1)"
test -n "$HOST_PORT"

probe() {
  local path="$1"
  python3.12 - "$HOST_PORT" "$path" <<'PY'
import json
import sys
from urllib.request import urlopen

port, path = sys.argv[1], sys.argv[2]
with urlopen(f"http://127.0.0.1:{port}{path}", timeout=2) as response:
    assert response.status == 200
    payload = json.load(response)
    assert payload["service"] == "alertam-cloud-infra-spike"
PY
}

wait_for_probe() {
  local path="$1"
  for _ in $(seq 1 30); do
    if probe "$path" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  docker logs "$NAME" >&2 || true
  return 1
}

wait_for_probe /healthz
probe /readyz

RUNTIME_UID="$(docker exec "$NAME" python -c 'import os; print(os.getuid())')"
test "$RUNTIME_UID" = "10001"

MOUNTS="$(docker inspect -f '{{json .Mounts}}' "$NAME")"
test "$MOUNTS" = "[]"

LOGS="$(docker logs "$NAME" 2>&1)"
if grep -Fq "$SENTINEL" <<<"$LOGS"; then
  echo "smoke failed: environment sentinel leaked to logs" >&2
  exit 1
fi

docker stop "$NAME" >/dev/null
docker start "$NAME" >/dev/null
HOST_PORT="$(docker port "$NAME" 8080/tcp | sed -n 's/.*://p' | head -n 1)"
test -n "$HOST_PORT"
wait_for_probe /healthz
probe /readyz

test -z "$(docker diff "$NAME")"

printf '%s\n' \
  "cloud smoke: /healthz=200" \
  "cloud smoke: /readyz=200" \
  "cloud smoke: uid=$RUNTIME_UID" \
  "cloud smoke: mounts=$MOUNTS" \
  "cloud smoke: restart=healthy" \
  "cloud smoke: filesystem-diff=empty" \
  "cloud smoke: logs=sanitized"
