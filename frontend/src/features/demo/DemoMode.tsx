import type { Pairing } from "../pairing/pairing";
import { StaticSnapshotProvider } from "../snapshot/SnapshotProvider";
import type { SnapshotState } from "../snapshot/useSnapshotPolling";
import { AppRoutes } from "../../app/router";
import { DEMO_RESPONSE } from "./demoData";

const DEMO_PAIRING: Pairing = {
  deviceId: "demo-pecem",
  viewSecret: "demo-only-not-a-real-secret",
  pairedAt: "2026-09-26T13:25:00-03:00",
};

const DEMO_STATE: SnapshotState = {
  status: "online",
  data: DEMO_RESPONSE,
  refresh: () => undefined,
};

export function DemoMode() {
  return (
    <StaticSnapshotProvider state={DEMO_STATE}>
      <AppRoutes
        pairing={DEMO_PAIRING}
        basePath="/demo"
        demoMode
      />
    </StaticSnapshotProvider>
  );
}
