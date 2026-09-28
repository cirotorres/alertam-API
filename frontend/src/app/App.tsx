import { BrowserRouter, useLocation } from "react-router-dom";

import { DemoMode } from "../features/demo/DemoMode";
import { EventProvider } from "../features/events/EventProvider";
import { PairingGate } from "../features/pairing/PairingGate";
import { PushProvider } from "../features/push/PushProvider";
import { SnapshotProvider } from "../features/snapshot/SnapshotProvider";
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
      {(pairing, resetPairing, sessionReady) => (
        <SnapshotProvider
          pairing={pairing}
          onAccessRevoked={resetPairing}
        >
          <EventProvider
            sessionReady={sessionReady}
            onAccessRevoked={resetPairing}
          >
            <PushProvider
              sessionReady={sessionReady}
              onAccessRevoked={resetPairing}
            >
              <AppRoutes
                pairing={pairing}
                onPairingCleared={resetPairing}
              />
            </PushProvider>
          </EventProvider>
        </SnapshotProvider>
      )}
    </PairingGate>
  );
}
