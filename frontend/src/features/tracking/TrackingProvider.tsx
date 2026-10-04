import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getTrackingEvents,
  listTrackedVessels,
  startTracking as startTrackingRequest,
  stopTracking as stopTrackingRequest,
  trackedVesselMatches,
  type TrackedVessel,
  type TrackingEventQuery,
  type TrackingForegroundFeedResponse,
  type TrackingTarget,
} from "../../api/trackingClient";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import {
  useTrackingPolling,
  type TrackingEventFetcher,
  type TrackingPollingStatus,
} from "./useTrackingPolling";
import {
  loadTrackingUnreadState,
  storeTrackingUnreadState,
} from "./trackingUnreadStorage";

export type TrackingStatus =
  | "idle"
  | "loading"
  | "online"
  | "offline"
  | "revoked";

export type TrackingState = {
  trackings: TrackedVessel[];
  status: TrackingStatus;
  newTrackingEvent: ReturnType<typeof useTrackingPolling>["newTrackingEvent"];
  mutationPending: boolean;
  mutationError: string | null;
  findTracking: (target: TrackingTarget | string) => TrackedVessel | null;
  isTracked: (target: TrackingTarget | string) => boolean;
  startTracking: (target: TrackingTarget) => Promise<boolean>;
  stopTracking: (trackedVesselId: string) => Promise<boolean>;
  refresh: () => Promise<boolean>;
  clearMutationError: () => void;
  isTrackingUnread?: (trackedVesselId: string) => boolean;
  markTrackingRead?: (trackedVesselId: string) => void;
};

type ListFetcher = (signal?: AbortSignal) => Promise<TrackedVessel[]>;
type StartFetcher = (
  target: TrackingTarget,
  signal?: AbortSignal,
) => Promise<TrackedVessel>;
type StopFetcher = (
  trackedVesselId: string,
  signal?: AbortSignal,
) => Promise<void>;

type TrackingProviderProps = {
  sessionReady: boolean;
  listFetcher?: ListFetcher;
  startFetcher?: StartFetcher;
  stopFetcher?: StopFetcher;
  eventFetcher?: TrackingEventFetcher;
  onAccessRevoked?: () => void;
  storageScope?: string;
  children: ReactNode;
};

const TrackingContext = createContext<TrackingState | null>(null);

function mergeStatus(
  sessionReady: boolean,
  listStatus: TrackingStatus,
  pollingStatus: TrackingPollingStatus,
): TrackingStatus {
  if (!sessionReady) return "idle";
  if (listStatus === "revoked" || pollingStatus === "revoked") return "revoked";
  if (listStatus === "loading" || pollingStatus === "loading") return "loading";
  if (listStatus === "offline" || pollingStatus === "offline") return "offline";
  return "online";
}

export function TrackingProvider({
  sessionReady,
  listFetcher = listTrackedVessels,
  startFetcher = startTrackingRequest,
  stopFetcher = stopTrackingRequest,
  eventFetcher = getTrackingEvents,
  onAccessRevoked,
  storageScope,
  children,
}: TrackingProviderProps) {
  const [trackings, setTrackings] = useState<TrackedVessel[]>([]);
  const [listStatus, setListStatus] = useState<TrackingStatus>("idle");
  const [mutationPending, setMutationPending] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const storedUnread = useMemo(
    () =>
      storageScope
        ? loadTrackingUnreadState(storageScope)
        : { cursor: null, unreadTrackedVesselIds: [] },
    [storageScope],
  );
  const [unreadTrackingIds, setUnreadTrackingIds] = useState<Set<string>>(
    () => new Set(storedUnread.unreadTrackedVesselIds),
  );

  const polling = useTrackingPolling(
    sessionReady,
    eventFetcher,
    onAccessRevoked,
    storedUnread.cursor,
  );

  const handleError = useCallback(
    (error: unknown, mutation = false) => {
      if (error instanceof AccessRevokedError) {
        setListStatus("revoked");
        onAccessRevoked?.();
        return;
      }
      if (mutation) {
        setMutationError("Não foi possível salvar o acompanhamento agora.");
      } else {
        setListStatus("offline");
      }
    },
    [onAccessRevoked],
  );

  const refresh = useCallback(async () => {
    if (!sessionReady) return false;
    const controller = new AbortController();
    try {
      const next = await listFetcher(controller.signal);
      setTrackings(next);
      setListStatus("online");
      return true;
    } catch (error) {
      if (!(error instanceof Error && error.name === "AbortError")) {
        handleError(error);
      }
      return false;
    }
  }, [handleError, listFetcher, sessionReady]);

  useEffect(() => {
    if (!sessionReady || polling.newTrackingEvent === null) {
      return;
    }
    void refresh();
  }, [polling.newTrackingEvent, refresh, sessionReady]);
  useEffect(() => {
    setUnreadTrackingIds(new Set(storedUnread.unreadTrackedVesselIds));
  }, [storedUnread]);

  useEffect(() => {
    if (!storageScope || polling.cursor === null) {
      return;
    }
    setUnreadTrackingIds((current) => {
      const next = new Set(current);
      for (const item of polling.newTrackingEvents) {
        next.add(item.tracked_vessel_id);
      }
      storeTrackingUnreadState(storageScope, {
        cursor: polling.cursor,
        unreadTrackedVesselIds: [...next],
      });
      return next;
    });
  }, [polling.cursor, polling.newTrackingEvents, storageScope]);


  useEffect(() => {
    setMutationError(null);
    if (!sessionReady) {
      setTrackings([]);
      setListStatus("idle");
      return;
    }

    setListStatus("loading");
    const controller = new AbortController();
    void listFetcher(controller.signal)
      .then((next) => {
        if (controller.signal.aborted) return;
        setTrackings(next);
        setListStatus("online");
      })
      .catch((error) => {
        if (
          controller.signal.aborted ||
          (error instanceof Error && error.name === "AbortError")
        ) {
          return;
        }
        handleError(error);
      });
    return () => controller.abort();
  }, [handleError, listFetcher, sessionReady]);

  const findTracking = useCallback(
    (target: TrackingTarget | string): TrackedVessel | null => {
      if (typeof target === "string") {
        return (
          trackings.find(
            (tracked) => tracked.vessel_identity === target,
          ) ?? null
        );
      }
      return (
        trackings.find((tracked) => trackedVesselMatches(tracked, target)) ??
        null
      );
    },
    [trackings],
  );

  const startTracking = useCallback(
    async (target: TrackingTarget): Promise<boolean> => {
      setMutationError(null);
      setMutationPending(true);
      try {
        const confirmed = await startFetcher(target);
        setTrackings((current) => {
          const next = current.filter(
            (item) => item.tracked_vessel_id !== confirmed.tracked_vessel_id,
          );
          next.push(confirmed);
          return next;
        });
        return true;
      } catch (error) {
        handleError(error, true);
        return false;
      } finally {
        setMutationPending(false);
      }
    },
    [handleError, startFetcher],
  );

  const stopTracking = useCallback(
    async (trackedVesselId: string): Promise<boolean> => {
      setMutationError(null);
      setMutationPending(true);
      try {
        await stopFetcher(trackedVesselId);
        setTrackings((current) =>
          current.filter(
            (item) => item.tracked_vessel_id !== trackedVesselId,
          ),
        );
        return true;
      } catch (error) {
        handleError(error, true);
        return false;
      } finally {
        setMutationPending(false);
      }
    },
    [handleError, stopFetcher],
  );

  const markTrackingRead = useCallback(
    (trackedVesselId: string) => {
      setUnreadTrackingIds((current) => {
        if (!current.has(trackedVesselId)) {
          return current;
        }
        const next = new Set(current);
        next.delete(trackedVesselId);
        if (storageScope) {
          storeTrackingUnreadState(storageScope, {
            cursor: polling.cursor ?? storedUnread.cursor,
            unreadTrackedVesselIds: [...next],
          });
        }
        return next;
      });
    },
    [polling.cursor, storageScope, storedUnread.cursor],
  );

  const value = useMemo<TrackingState>(
    () => ({
      trackings,
      status: mergeStatus(sessionReady, listStatus, polling.status),
      newTrackingEvent: polling.newTrackingEvent,
      mutationPending,
      mutationError,
      findTracking,
      isTracked: (target) => findTracking(target) !== null,
      startTracking,
      stopTracking,
      refresh,
      clearMutationError: () => setMutationError(null),
      isTrackingUnread: (trackedVesselId) =>
        unreadTrackingIds.has(trackedVesselId),
      markTrackingRead,
    }),
    [
      findTracking,
      listStatus,
      mutationError,
      mutationPending,
      markTrackingRead,
      polling.newTrackingEvent,
      polling.status,
      refresh,
      sessionReady,
      startTracking,
      stopTracking,
      trackings,
      unreadTrackingIds,
    ],
  );

  return (
    <TrackingContext.Provider value={value}>
      {children}
    </TrackingContext.Provider>
  );
}

export function useOptionalTracking(): TrackingState | null {
  return useContext(TrackingContext);
}

export function useTracking(): TrackingState {
  const state = useOptionalTracking();
  if (state === null) {
    throw new Error("TrackingProvider ausente.");
  }
  return state;
}

export function StaticTrackingProvider({
  state,
  children,
}: {
  state: TrackingState;
  children: ReactNode;
}) {
  return (
    <TrackingContext.Provider value={state}>
      {children}
    </TrackingContext.Provider>
  );
}

export type {
  TrackingEventFetcher,
  TrackingEventQuery,
  TrackingForegroundFeedResponse,
};
