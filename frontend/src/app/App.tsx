import { BrowserRouter, useLocation } from "react-router-dom";

import { DemoMode } from "../features/demo/DemoMode";
import { EventProvider } from "../features/events/EventProvider";
import { PairingGate } from "../features/pairing/PairingGate";
import { PushProvider } from "../features/push/PushProvider";
import { SnapshotProvider } from "../features/snapshot/SnapshotProvider";
import { TrackingProvider } from "../features/tracking/TrackingProvider";
import { AppRoutes } from "./router";

export function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

function AppContent() {
  const location = useLocation();
  const isDemo =
    location.pathname === "/demo" ||
    location.pathname.startsWith("/demo/");

  if (isDemo) {
    return <DemoMode />;
  }

  return (
    <PairingGate>
      {(
        pairing,
        resetPairing,
        sessionReady,
        handleAccessRevoked,
        sessionInfo,
      ) => (
        <SnapshotProvider
          key={sessionInfo?.installationId ?? `pending:${pairing.deviceId}`}
          pairing={pairing}
          onAccessRevoked={handleAccessRevoked}
        >
          <EventProvider
            sessionReady={sessionReady}
            onAccessRevoked={handleAccessRevoked}
          >
            <TrackingProvider
              sessionReady={sessionReady}
              onAccessRevoked={handleAccessRevoked}
            >
              <PushProvider
                sessionReady={sessionReady}
                onAccessRevoked={handleAccessRevoked}
              >
                <AppRoutes
                  pairing={pairing}
                  installation={sessionInfo}
                  onPairingCleared={resetPairing}
                  onAccessRevoked={handleAccessRevoked}
                />
              </PushProvider>
            </TrackingProvider>
          </EventProvider>
        </SnapshotProvider>
      )}
    </PairingGate>
  );
}
