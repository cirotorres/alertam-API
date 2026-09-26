import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../../api/contract";
import type { Pairing } from "../pairing/pairing";
import {
  SnapshotProvider,
  useSnapshotState,
} from "./SnapshotProvider";

const pairing: Pairing = {
  deviceId: "pecem-01",
  viewSecret: "Abcdefghijklmnopqrstuvwxyz0123456789_-ABCDE",
  pairedAt: "2026-09-26T09:40:00-03:00",
};

const response = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
});

function Probe() {
  const state = useSnapshotState();
  return <output>{state.status}</output>;
}

test("provides_polling_state_to_children", async () => {
  const fetcher = vi.fn().mockResolvedValue(response);

  render(
    <SnapshotProvider pairing={pairing} fetcher={fetcher}>
      <Probe />
    </SnapshotProvider>,
  );

  expect(await screen.findByText("online")).toBeInTheDocument();
});
