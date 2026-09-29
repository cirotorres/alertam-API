import { Route, Routes } from "react-router-dom";

import type { AlertDetailFetcher } from "../features/events/useAlertDetail";
import type { Pairing } from "../features/pairing/pairing";
import { AlertsPage } from "../pages/AlertsPage";
import { AboutPage } from "../pages/AboutPage";
import { ConfigPage } from "../pages/ConfigPage";
import { HistoryPage } from "../pages/HistoryPage";
import { MapPage } from "../pages/MapPage";
import { TrackedVesselsPage } from "../pages/TrackedVesselsPage";
import { WeatherPage } from "../pages/WeatherPage";
import { AppShell } from "./AppShell";

type AppRoutesProps = {
  pairing: Pairing;
  onPairingCleared?: () => void;
  basePath?: string;
  demoMode?: boolean;
  alertDetailFetcher?: AlertDetailFetcher;
};

export function AppRoutes({
  pairing,
  onPairingCleared,
  basePath = "",
  demoMode = false,
  alertDetailFetcher,
}: AppRoutesProps) {
  const routePath = (suffix: string) =>
    basePath ? `${basePath}${suffix}` : suffix || "/";

  return (
    <Routes>
      <Route
        element={
          <AppShell
            pairing={pairing}
            onPairingCleared={onPairingCleared}
            basePath={basePath}
            demoMode={demoMode}
            alertDetailFetcher={alertDetailFetcher}
          />
        }
      >
        <Route path={routePath("")} element={<MapPage />} />
        <Route path={routePath("/alertas")} element={<AlertsPage />} />
        <Route path={routePath("/historico")} element={<HistoryPage />} />
        <Route path={routePath("/acompanhados")} element={<TrackedVesselsPage />} />
        <Route path={routePath("/tempo")} element={<WeatherPage />} />
        <Route path={routePath("/config")} element={<ConfigPage />} />
        <Route path={routePath("/sobre")} element={<AboutPage />} />
      </Route>
    </Routes>
  );
}
