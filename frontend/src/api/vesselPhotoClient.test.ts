import { afterEach, expect, test, vi } from "vitest";

import type { Pairing } from "../features/pairing/pairing";
import { getVesselPhoto } from "./vesselPhotoClient";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "view-secret",
  pairedAt: "2026-09-26T20:00:00-03:00",
};

afterEach(() => vi.unstubAllGlobals());

test("fetches_photo_with_same_mobile_credentials", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    imo: "1234567",
    photo_url: "https://upload.wikimedia.org/navio.jpg",
    author: "Autor",
    license: "CC BY-SA 4.0",
    source_url: "https://commons.wikimedia.org/wiki/File:Navio.jpg",
  }), { status: 200, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);

  const result = await getVesselPhoto(pairing, "1234567");

  expect(result.photo_url).toContain("wikimedia.org");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/devices/pecem-01/vessels/1234567/photo",
    expect.objectContaining({
      credentials: "same-origin",
      headers: { Authorization: "Bearer view-secret" },
    }),
  );
});
