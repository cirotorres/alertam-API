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

import type { ManeuverEventFeedItem, VesselV1 } from "../api/contract";
import { BottomNav, type BottomNavItem, type BottomTab } from "../components/BottomNav";
import { useEventState } from "../features/events/EventProvider";
import { AlertDetailSheet } from "../features/events/AlertDetailSheet";
import {
  useAlertDetail,
  type AlertDetailFetcher,
} from "../features/events/useAlertDetail";
import { Drawer } from "../components/Drawer";
import { Header } from "../components/Header";
import type { Pairing } from "../features/pairing/pairing";
import { usePush } from "../features/push/PushProvider";
import { useForegroundHeartbeat } from "../features/push/useForegroundHeartbeat";
import { useSnapshotState } from "../features/snapshot/SnapshotProvider";
import type { SnapshotState } from "../features/snapshot/useSnapshotPolling";
import { useOptionalTracking } from "../features/tracking/TrackingProvider";
import { VesselSheet } from "../features/vessels/VesselSheet";
import { useVesselPhoto } from "../features/vessels/useVesselPhoto";

type AppShellProps = {
  pairing: Pairing;
  onPairingCleared?: () => void;
  basePath?: string;
  demoMode?: boolean;
  alertDetailFetcher?: AlertDetailFetcher;
};

const noop = () => undefined;

function maneuverPreferenceEnabled(
  event: ManeuverEventFeedItem,
  preferences: {
    confirmed: boolean;
    updated: boolean;
    completed: boolean;
    cancelled: boolean;
  },
): boolean {
  const key = event.event_type.toLowerCase() as
    | "confirmed"
    | "updated"
    | "completed"
    | "cancelled";
  return preferences[key];
}

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
  onPairingCleared = noop,
  basePath = "",
  demoMode = false,
  alertDetailFetcher,
}: AppShellProps) {
  const snapshotState = useSnapshotState();
  const eventState = useEventState();
  const pushState = usePush();
  const trackingState = useOptionalTracking();
  const navigate = useNavigate();
  const location = useLocation();
  const currentParams = new URLSearchParams(location.search);
  const eventId = currentParams.get("event");
  const trackId = currentParams.get("track");
  const alertEventId = trackId === null ? eventId : null;
  const alertDetail = useAlertDetail(
    alertEventId,
    alertDetailFetcher,
    onPairingCleared,
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [documentVisible, setDocumentVisible] = useState(
    () => document.visibilityState === "visible",
  );
  const [selectedVessel, setSelectedVessel] = useState<VesselV1 | null>(null);
  const [renderedVessel, setRenderedVessel] = useState<VesselV1 | null>(null);
  const [dismissedNoticeKey, setDismissedNoticeKey] = useState<string | null>(null);
  const [activeBottomTab, setActiveBottomTab] =
    useState<BottomTab>("maneuvers");
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const vesselTriggerRef = useRef<HTMLElement | null>(null);

  useForegroundHeartbeat(
    pushState.active && !demoMode,
    undefined,
    onPairingCleared,
  );

  useEffect(() => {
    const handleVisibility = () => {
      setDocumentVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

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

  const closeAlertDetail = useCallback(() => {
    const params = new URLSearchParams(location.search);
    params.delete("event");
    const search = params.toString();
    navigate(
      {
        pathname: location.pathname,
        search: search ? `?${search}` : "",
        hash: location.hash,
      },
      { replace: true },
    );
  }, [location.hash, location.pathname, location.search, navigate]);

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
    if (alertEventId === null) return;
    setDrawerOpen(false);
    setSelectedVessel(null);
    vesselTriggerRef.current = null;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeAlertDetail();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [alertEventId, closeAlertDetail]);

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

  const maneuverNotice = (() => {
    const event = eventState.newEvent;
    if (!event) return null;
    const generalEnabled = maneuverPreferenceEnabled(
      event,
      pushState.preferences,
    );
    if (generalEnabled) {
      return {
        key: `alert:${event.event_id}`,
        kind: "alert" as const,
        vesselName: event.vessel_name,
        label: "Novo alerta operacional",
        button: "Ver alerta",
        url: routePath(`/alertas?event=${event.event_id}`),
      };
    }
    const tracked = trackingState?.findTracking({
      vessel_identity: event.vessel_identity,
      vessel_imo: event.vessel_imo,
      vessel_name: event.vessel_name,
    });
    if (!tracked) return null;
    return {
      key: `tracking:${event.event_id}`,
      kind: "tracking" as const,
      vesselName: event.vessel_name,
      label: "Novo acompanhamento",
      button: "Ver acompanhamento",
      url: routePath(
        `/acompanhados?track=${tracked.tracked_vessel_id}&event=${event.event_id}`,
      ),
    };
  })();

  const trackingNotice = (() => {
    const item = trackingState?.newTrackingEvent;
    if (!item) return null;
    if (
      maneuverNotice?.kind === "alert" &&
      item.event.maneuver_id === eventState.newEvent?.maneuver_id
    ) {
      return null;
    }
    return {
      key: `tracking:${item.event.event_id}`,
      kind: "tracking" as const,
      vesselName: item.event.vessel_name,
      label: "Novo acompanhamento",
      button: "Ver acompanhamento",
      url: routePath(
        `/acompanhados?track=${item.tracked_vessel_id}&event=${item.event.event_id}`,
      ),
    };
  })();

  const foregroundNotice = maneuverNotice ?? trackingNotice;
  const visibleForegroundNotice =
    foregroundNotice?.key === dismissedNoticeKey ? null : foregroundNotice;

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
    routePath("/acompanhados"),
    routePath("/tempo"),
  ].includes(location.pathname);

  const bottomNavActive: BottomNavItem | null =
    location.pathname === routePath("/acompanhados")
      ? null
      : location.pathname === routePath("/tempo")
        ? "weather"
        : activeBottomTab;

  const handleBottomTabChange = (tab: BottomNavItem) => {
    if (tab === "weather") {
      if (location.pathname !== routePath("/tempo")) {
        navigate(routePath("/tempo"));
      }
      return;
    }

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
      {!demoMode && documentVisible && visibleForegroundNotice ? (
        <div
          className="foreground-alert"
          role="status"
          aria-label={visibleForegroundNotice.label}
        >
          <span>
            {visibleForegroundNotice.kind === "alert" ? "Novo alerta" : "Atualização acompanhada"}:{" "}
            <strong>{visibleForegroundNotice.vesselName}</strong>
          </span>
          <div className="foreground-alert__actions">
            <button
              type="button"
              onClick={() => navigate(visibleForegroundNotice.url)}
            >
              {visibleForegroundNotice.button}
            </button>
            <button
              type="button"
              className="foreground-alert__close"
              aria-label="Fechar aviso"
              onClick={() => setDismissedNoticeKey(visibleForegroundNotice.key)}
            >
              ×
            </button>
          </div>
        </div>
      ) : null}
      <main className="mobile-content">
        <Outlet context={outletContext} />
      </main>
      {showBottomNav ? (
        <BottomNav
          active={bottomNavActive}
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
          photoError={vesselPhoto.error}
          trackingControls={trackingState ?? undefined}
        />
      ) : null}
      <AlertDetailSheet
        open={alertEventId !== null}
        state={alertDetail}
        selectedEventId={alertEventId}
        onClose={closeAlertDetail}
        onRetry={alertDetail.retry}
        trackingControls={trackingState ?? undefined}
      />
    </div>
  );
}

export function useShellContext(): ShellOutletContext {
  return useOutletContext<ShellOutletContext>();
}
