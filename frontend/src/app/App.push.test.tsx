import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

const INSTALL_A = "11111111-2222-4333-8444-555555555555";
const INSTALL_B = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";

const wiring = vi.hoisted(() => ({
  reset: vi.fn(),
  revoked: vi.fn(),
  snapshotProps: [] as Array<Record<string, unknown>>,
  eventProps: [] as Array<Record<string, unknown>>,
  trackingProps: [] as Array<Record<string, unknown>>,
  pushProps: [] as Array<Record<string, unknown>>,
  routeProps: [] as Array<Record<string, unknown>>,
  snapshotMounts: 0,
  eventMounts: 0,
  trackingMounts: 0,
}));

vi.mock("../features/pairing/PairingGate", async () => {
  const React = await import("react");

  return {
    PairingGate: ({ children }: any) => {
      const [current, setCurrent] = React.useState({
        pairing: {
          deviceId: "pecem-a",
          viewSecret: null,
          pairedAt: "2026-09-30T18:00:00Z",
        },
        session: {
          deviceId: "pecem-a",
          installationId: INSTALL_A,
          displayCode: "K7M4Q2",
          platform: "ios",
        },
      });

      return (
        <>
          <button
            type="button"
            onClick={() => setCurrent({
              pairing: {
                deviceId: "pecem-b",
                viewSecret: null,
                pairedAt: "2026-09-30T18:05:00Z",
              },
              session: {
                deviceId: "pecem-b",
                installationId: INSTALL_B,
                displayCode: "8P2R6X",
                platform: "android",
              },
            })}
          >
            SWITCH TEST SESSION
          </button>
          {children(
            current.pairing,
            wiring.reset,
            true,
            wiring.revoked,
            current.session,
          )}
        </>
      );
    },
  };
});

vi.mock("../features/snapshot/SnapshotProvider", async () => {
  const React = await import("react");

  return {
    SnapshotProvider: (props: any) => {
      wiring.snapshotProps.push(props);
      React.useEffect(() => {
        wiring.snapshotMounts += 1;
      }, []);
      return props.children;
    },
  };
});

vi.mock("../features/events/EventProvider", async () => {
  const React = await import("react");
  return {
    EventProvider: (props: any) => {
      wiring.eventProps.push(props);
      React.useEffect(() => {
        wiring.eventMounts += 1;
      }, []);
      return props.children;
    },
  };
});

vi.mock("../features/tracking/TrackingProvider", async () => {
  const React = await import("react");
  return {
    TrackingProvider: (props: any) => {
      wiring.trackingProps.push(props);
      React.useEffect(() => {
        wiring.trackingMounts += 1;
      }, []);
      return props.children;
    },
  };
});

vi.mock("../features/push/PushProvider", () => ({
  PushProvider: (props: any) => {
    wiring.pushProps.push(props);
    return props.children;
  },
}));

vi.mock("./router", () => ({
  AppRoutes: (props: any) => {
    wiring.routeProps.push(props);
    return <div>ROUTES</div>;
  },
}));

vi.mock("../features/demo/DemoMode", () => ({
  DemoMode: () => <div>DEMO</div>,
}));

import { App } from "./App";

test("wires access revocation separately from manual pairing reset", () => {
  render(<App />);

  expect(screen.getByText("ROUTES")).toBeInTheDocument();
  expect(wiring.snapshotProps.at(-1)?.onAccessRevoked).toBe(wiring.revoked);
  expect(wiring.eventProps.at(-1)?.onAccessRevoked).toBe(wiring.revoked);
  expect(wiring.trackingProps.at(-1)?.onAccessRevoked).toBe(wiring.revoked);
  expect(wiring.pushProps.at(-1)?.onAccessRevoked).toBe(wiring.revoked);

  expect(wiring.routeProps.at(-1)?.onPairingCleared).toBe(wiring.reset);
  expect(wiring.routeProps.at(-1)?.onAccessRevoked).toBe(wiring.revoked);
  expect(wiring.routeProps.at(-1)?.installation).toEqual(
    expect.objectContaining({
      installationId: INSTALL_A,
      displayCode: "K7M4Q2",
    }),
  );
});

test("changing installation id remounts snapshot events and tracking", async () => {
  wiring.snapshotMounts = 0;
  wiring.eventMounts = 0;
  wiring.trackingMounts = 0;
  render(<App />);

  await waitFor(() => {
    expect(wiring.snapshotMounts).toBe(1);
    expect(wiring.eventMounts).toBe(1);
    expect(wiring.trackingMounts).toBe(1);
  });

  fireEvent.click(
    screen.getByRole("button", { name: "SWITCH TEST SESSION" }),
  );

  await waitFor(() => {
    expect(wiring.snapshotMounts).toBe(2);
    expect(wiring.eventMounts).toBe(2);
    expect(wiring.trackingMounts).toBe(2);
  });
  expect(wiring.routeProps.at(-1)?.installation).toEqual(
    expect.objectContaining({
      installationId: INSTALL_B,
      displayCode: "8P2R6X",
    }),
  );
});
