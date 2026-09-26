import { beforeEach, expect, test } from "vitest";

import type { Pairing } from "./pairing";
import {
  PAIRING_STORAGE_KEY,
  clearPairing,
  loadPairing,
  savePairing,
} from "./pairingStorage";

const PAIRING: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
};

beforeEach(() => {
  localStorage.clear();
});

test("round_trips_versioned_pairing", () => {
  savePairing(PAIRING);

  expect(loadPairing()).toEqual(PAIRING);
  expect(JSON.parse(localStorage.getItem(PAIRING_STORAGE_KEY) ?? "{}")).toEqual(PAIRING);
});

test("corrupt_pairing_is_removed_and_ignored", () => {
  localStorage.setItem(PAIRING_STORAGE_KEY, "{broken");

  expect(loadPairing()).toBeNull();
  expect(localStorage.getItem(PAIRING_STORAGE_KEY)).toBeNull();
});

test("invalid_pairing_shape_is_removed_and_ignored", () => {
  localStorage.setItem(
    PAIRING_STORAGE_KEY,
    JSON.stringify({ ...PAIRING, viewSecret: "curto" }),
  );

  expect(loadPairing()).toBeNull();
  expect(localStorage.getItem(PAIRING_STORAGE_KEY)).toBeNull();
});

test("clear_pairing_removes_local_credentials", () => {
  savePairing(PAIRING);

  clearPairing();

  expect(loadPairing()).toBeNull();
  expect(localStorage.getItem(PAIRING_STORAGE_KEY)).toBeNull();
});
