import {
  PairingCodeRedeemError,
  redeemPairingCode,
} from "./pairingCodeClient";


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


test("redeem returns in-memory pairing ticket candidate", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        device_id: "pecem-remoto",
        pairing_ticket: "T".repeat(43),
        expires_at: "2026-10-02T17:05:00Z",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  const pairing = await redeemPairingCode("483721");

  expect(pairing).toEqual(
    expect.objectContaining({
      deviceId: "pecem-remoto",
      viewSecret: null,
      pairingTicket: "T".repeat(43),
    }),
  );
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/mobile/pairing/code",
    expect.objectContaining({
      method: "POST",
      credentials: "same-origin",
      body: JSON.stringify({ code: "483721" }),
    }),
  );
  expect(localStorage.length).toBe(0);
});


test.each([
  [401, "invalid"],
  [429, "rate-limited"],
  [503, "temporary"],
] as const)("redeem maps HTTP %s to %s error", async (status, kind) => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status })),
  );

  await expect(redeemPairingCode("483721")).rejects.toMatchObject({
    name: PairingCodeRedeemError.name,
    kind,
  });
});
