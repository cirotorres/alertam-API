import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
} from "react-router-dom";

import type { VesselV1 } from "../api/contract";
import { BottomNav, type BottomTab } from "../components/BottomNav";
import { Drawer } from "../components/Drawer";
import { Header } from "../components/Header";
import type { Pairing } from "../features/pairing/pairing";
import { useSnapshotState } from "../features/snapshot/SnapshotProvider";
import type { SnapshotState } from "../features/snapshot/useSnapshotPolling";
import { VesselSheet } from "../features/vessels/VesselSheet";
import { useVesselPhoto } from "../features/vessels/useVesselPhoto";

type AppShellProps = {
  pairing: Pairing;
  onPairingCleared?: () => void;
  basePath?: string;
  demoMode?: boolean;
};

export type ShellOutletContext = {
  pairing: Pairing;
  snapshotState: SnapshotState;
  activeBottomTab: BottomTab;
  setActiveBottomTab: (tab: BottomTab) => void;
  selectVessel: (vessel: VesselV1) => void;
  onPairingCleared: () => void;
  basePath: string;
  demoMode: boolean;
};
export function AppShell({
  pairing,
  onPairingCleared = () => undefined,
  basePath = "",
  demoMode = false,
}: AppShellProps) {
  const snapshotState = useSnapshotState();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedVessel, setSelectedVessel] = useState<VesselV1 | null>(null);
  const [renderedVessel, setRenderedVessel] = useState<VesselV1 | null>(null);
  const [activeBottomTab, setActiveBottomTab] =
    useState<BottomTab>("maneuvers");
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const vesselTriggerRef = useRef<HTMLElement | null>(null);

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
    queueMicrotask(() => menuButtonRef.current?.focus());
  }, []);

  const openDrawer = useCallback(() => {
    setSelectedVessel(null);
    vesselTriggerRef.current = null;
    setDrawerOpen(true);
  }, []);

  const closeVessel = useCallback(() => {
    setSelectedVessel(null);
    const trigger = vesselTriggerRef.current;
    vesselTriggerRef.current = null;
    queueMicrotask(() => trigger?.focus());
  }, []);
  const selectVessel = useCallback((vessel: VesselV1) => {
    vesselTriggerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setDrawerOpen(false);
    setRenderedVessel(vessel);
    setSelectedVessel(vessel);
  }, []);

  useEffect(() => {
    if (!selectedVessel || drawerOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeVessel();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [closeVessel, drawerOpen, selectedVessel]);

  useEffect(() => {
    if (selectedVessel || !renderedVessel) return;

    const timeoutId = window.setTimeout(() => setRenderedVessel(null), 220);
    return () => window.clearTimeout(timeoutId);
  }, [renderedVessel, selectedVessel]);

  const vesselPhoto = useVesselPhoto({
    pairing,
    vessel: renderedVessel,
    open: selectedVessel !== null,
    demoMode,
  });

  const lastCollectionAt =
    snapshotState.data?.snapshot.collector.last_collection_at ?? null;

  const rootPath = basePath || "/";
  const routePath = (suffix: string) =>
    basePath ? `${basePath}${suffix}` : suffix || "/";

  const outletContext: ShellOutletContext = {
    pairing,
    snapshotState,
    activeBottomTab,
    setActiveBottomTab,
    selectVessel,
    onPairingCleared,
    basePath,
    demoMode,
  };

  const showBottomNav = [
    rootPath,
    routePath("/alertas"),
    routePath("/historico"),
  ].includes(location.pathname);

  const handleBottomTabChange = (tab: BottomTab) => {
    setActiveBottomTab(tab);
    if (location.pathname !== rootPath) {
      navigate(rootPath);
    }
  };
  return (
    <div className="mobile-app">
      <Header
        status={snapshotState.status}
        lastCollectionAt={lastCollectionAt}
        demoMode={demoMode}
        onMenu={openDrawer}
        menuButtonRef={menuButtonRef}
      />
      <Drawer
        open={drawerOpen}
        onClose={closeDrawer}
        basePath={basePath}
        demoMode={demoMode}
      />
      {demoMode ? (
        <div className="demo-banner" role="note">
          Dados fictícios para validação visual · nenhuma consulta à API real
        </div>
      ) : null}
      <main className="mobile-content">
        <Outlet context={outletContext} />
      </main>
      {showBottomNav ? (
        <BottomNav
          active={activeBottomTab}
          onChange={handleBottomTabChange}
        />
      ) : null}
      {renderedVessel ? (
        <VesselSheet
          vessel={renderedVessel}
          open={selectedVessel !== null}
          onClose={closeVessel}
          photo={vesselPhoto.photo}
          photoLoading={vesselPhoto.loading}
        />
      ) : null}
    </div>
  );
}

export function useShellContext(): ShellOutletContext {
  return useOutletContext<ShellOutletContext>();
}
