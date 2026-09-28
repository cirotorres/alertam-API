import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

const wiring = vi.hoisted(() => ({
  reset: vi.fn(),
  pushProps: [] as Array<Record<string, unknown>>,
}));

vi.mock("../features/pairing/PairingGate", () => ({
  PairingGate: ({ children }: any) => children(
    {
      deviceId: "pecem-01",
      viewSecret: null,
      pairedAt: "2026-09-27T18:00:00Z",
    },
    wiring.reset,
    true,
  ),
}));

vi.mock("../features/snapshot/SnapshotProvider", () => ({
  SnapshotProvider: ({ children }: any) => children,
}));

vi.mock("../features/events/EventProvider", () => ({
  EventProvider: ({ children }: any) => children,
}));

vi.mock("../features/push/PushProvider", () => ({
  PushProvider: (props: any) => {
    wiring.pushProps.push(props);
    return props.children;
  },
}));

vi.mock("./router", () => ({
  AppRoutes: () => <div>ROUTES</div>,
}));

vi.mock("../features/demo/DemoMode", () => ({
  DemoMode: () => <div>DEMO</div>,
}));

import { App } from "./App";


test("wires_session_ready_and_pairing_reset_into_push_provider", () => {
  render(<App />);

  expect(screen.getByText("ROUTES")).toBeInTheDocument();
  expect(wiring.pushProps).toHaveLength(1);
  expect(wiring.pushProps[0].sessionReady).toBe(true);
  expect(wiring.pushProps[0].onAccessRevoked).toBe(wiring.reset);
});
