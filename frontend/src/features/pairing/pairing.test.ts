import { beforeEach, expect, test, vi } from "vitest";

import { clearPairingFragment, parsePairingFragment } from "./pairing";

const TOKEN = "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE";

beforeEach(() => {
  window.history.replaceState({}, "", "/mobile?modo=teste");
});

test("parses_valid_pairing_fragment", () => {
  const parsed = parsePairingFragment(
    `#/pair/pecem%2D01?token=${TOKEN}`,
  );

  expect(parsed).toEqual({
    deviceId: "pecem-01",
    viewSecret: TOKEN,
  });
});

test.each([
  "#/pair/pecem-01",
  "#/pair/pecem-01?token=curto",
  `#/pair/?token=${TOKEN}`,
  `#/pair/%E0%A4%A?token=${TOKEN}`,
  "#/outra-rota/pecem-01?token=" + TOKEN,
])("rejects_malformed_pairing_fragment: %s", (hash) => {
  expect(parsePairingFragment(hash)).toBeNull();
});

test("clear_pairing_fragment_removes_secret_and_preserves_path_and_search", () => {
  window.history.replaceState({}, "", `/mobile?modo=teste#/pair/pecem-01?token=${TOKEN}`);
  const spy = vi.spyOn(window.history, "replaceState");

  clearPairingFragment(window.history);

  expect(spy).toHaveBeenCalledWith(
    window.history.state,
    "",
    "/mobile?modo=teste",
  );
  expect(spy.mock.calls.flat().join(" ")).not.toContain(TOKEN);
});
