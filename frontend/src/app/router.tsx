import { Route, Routes } from "react-router-dom";

import type { Pairing } from "../features/pairing/pairing";
import { AlertsPage } from "../pages/AlertsPage";
import { AboutPage } from "../pages/AboutPage";
import { ConfigPage } from "../pages/ConfigPage";
import { HistoryPage } from "../pages/HistoryPage";
import { MapPage } from "../pages/MapPage";
import { AppShell } from "./AppShell";

type AppRoutesProps = {
  pairing: Pairing;
  onPairingCleared?: () => void;
  onInstall?: () => void;
};

export function AppRoutes({
  pairing,
  onPairingCleared,
  onInstall,
}: AppRoutesProps) {
  return (
    <Routes>
      <Route
        element={
          <AppShell
            pairing={pairing}
            onPairingCleared={onPairingCleared}
            onInstall={onInstall}
          />
        }
      >
        <Route path="/" element={<MapPage />} />
        <Route path="/alertas" element={<AlertsPage />} />
        <Route path="/historico" element={<HistoryPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/sobre" element={<AboutPage />} />
      </Route>
    </Routes>
  );
}
