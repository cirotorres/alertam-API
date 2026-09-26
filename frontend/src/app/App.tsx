import { BrowserRouter, useLocation } from "react-router-dom";

import { DemoMode } from "../features/demo/DemoMode";
import { PairingGate } from "../features/pairing/PairingGate";
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
      {(pairing, resetPairing) => (
        <SnapshotProvider
          pairing={pairing}
          onAccessRevoked={resetPairing}
        >
          <AppRoutes
            pairing={pairing}
            onPairingCleared={resetPairing}
          />
        </SnapshotProvider>
      )}
    </PairingGate>
  );
}
