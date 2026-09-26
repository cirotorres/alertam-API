import snapshot from "../src/test/fixtures/mobile_snapshot_v1.json" with { type: "json" };

export const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";
export const PAIRING_KEY = "alertam.mobile.pairing.v1";

export const onlineResponse = {
  snapshot,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
};

export const staleResponse = {
  ...onlineResponse,
  meta: {
    ...onlineResponse.meta,
    age_seconds: 180,
    collector_online: false,
  },
};

export function storedPairing(deviceId = "pecem-01") {
  return {
    deviceId,
    viewSecret: TOKEN,
    pairedAt: "2026-09-26T09:40:00-03:00",
  };
}
