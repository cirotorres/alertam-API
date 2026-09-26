import { BrowserRouter } from "react-router-dom";

import { PairingGate } from "../features/pairing/PairingGate";
import { SnapshotProvider } from "../features/snapshot/SnapshotProvider";
import { AppRoutes } from "./router";

export function App() {
  return (
    <PairingGate>
      {(pairing, resetPairing) => (
        <BrowserRouter>
          <SnapshotProvider
            pairing={pairing}
            onAccessRevoked={resetPairing}
          >
            <AppRoutes
              pairing={pairing}
              onPairingCleared={resetPairing}
            />
          </SnapshotProvider>
        </BrowserRouter>
      )}
    </PairingGate>
  );
}
