import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Outlet, useOutletContext } from "react-router-dom";

import type { VesselV1 } from "../api/contract";
import { Drawer } from "../components/Drawer";
import { Header } from "../components/Header";
import type { Pairing } from "../features/pairing/pairing";
import { useSnapshotState } from "../features/snapshot/SnapshotProvider";
import type { SnapshotState } from "../features/snapshot/useSnapshotPolling";
import { VesselSheet } from "../features/vessels/VesselSheet";

type AppShellProps = {
  pairing: Pairing;
  onPairingCleared?: () => void;
};

export type ShellOutletContext = {
  pairing: Pairing;
  snapshotState: SnapshotState;
  selectVessel: (vessel: VesselV1) => void;
  onPairingCleared: () => void;
};
export function AppShell({
  pairing,
  onPairingCleared = () => undefined,
}: AppShellProps) {
  const snapshotState = useSnapshotState();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedVessel, setSelectedVessel] = useState<VesselV1 | null>(null);
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

  const lastCollectionAt =
    snapshotState.data?.snapshot.collector.last_collection_at ?? null;

  const outletContext: ShellOutletContext = {
    pairing,
    snapshotState,
    selectVessel,
    onPairingCleared,
  };
  return (
    <div className="mobile-app">
      <Header
        status={snapshotState.status}
        lastCollectionAt={lastCollectionAt}
        onMenu={openDrawer}
        menuButtonRef={menuButtonRef}
      />
      <Drawer open={drawerOpen} onClose={closeDrawer} />
      <main className="mobile-content">
        <Outlet context={outletContext} />
      </main>
      {selectedVessel ? (
        <>
          <button
            className="vessel-sheet-backdrop"
            type="button"
            aria-label="Fechar ficha"
            onClick={closeVessel}
          />
          <VesselSheet vessel={selectedVessel} open onClose={closeVessel} />
        </>
      ) : null}
    </div>
  );
}

export function useShellContext(): ShellOutletContext {
  return useOutletContext<ShellOutletContext>();
}
