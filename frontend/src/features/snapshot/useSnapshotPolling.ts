import { useCallback, useEffect, useRef, useState } from "react";

import type { SnapshotReadResponse } from "../../api/contract";
import {
  AccessRevokedError,
  SnapshotUnavailableError,
  TemporaryApiError,
  UnsupportedSnapshotError,
  getSnapshot,
} from "../../api/snapshotClient";
import type { Pairing } from "../pairing/pairing";
import { clearPairing } from "../pairing/pairingStorage";

export type SnapshotStatus =
  | "loading"
  | "online"
  | "stale"
  | "waiting"
  | "offline"
  | "revoked"
  | "unsupported";
export type SnapshotState = {
  status: SnapshotStatus;
  data: SnapshotReadResponse | null;
  refresh: () => void;
};

export type SnapshotFetcher = (
  pairing: Pairing,
  signal?: AbortSignal,
) => Promise<SnapshotReadResponse>;

const POLL_INTERVAL_MS = 30_000;

export function useSnapshotPolling(
  pairing: Pairing,
  fetcher: SnapshotFetcher = getSnapshot,
): SnapshotState {
  const [status, setStatus] = useState<SnapshotStatus>("loading");
  const [data, setData] = useState<SnapshotReadResponse | null>(null);
  const refreshRef = useRef<(() => void) | null>(null);
  useEffect(() => {
    setStatus("loading");
    setData(null);

    let disposed = false;
    let terminal = false;
    let busy = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const clearTimer = () => {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const schedule = () => {
      clearTimer();
      if (disposed || terminal || document.visibilityState !== "visible") {
        return;
      }
      timer = setTimeout(() => {
        void runFetch();
      }, POLL_INTERVAL_MS);
    };
    const runFetch = async () => {
      if (
        disposed ||
        terminal ||
        busy ||
        document.visibilityState !== "visible"
      ) {
        return;
      }

      busy = true;
      clearTimer();
      const requestController = new AbortController();
      controller = requestController;

      try {
        const next = await fetcher(pairing, requestController.signal);
        if (disposed || requestController.signal.aborted) {
          return;
        }
        setData(next);
        setStatus(next.meta.collector_online ? "online" : "stale");
      } catch (error) {
        if (
          disposed ||
          requestController.signal.aborted ||
          (error instanceof Error && error.name === "AbortError")
        ) {
          return;
        }

        if (error instanceof AccessRevokedError) {
          terminal = true;
          clearPairing();
          setStatus("revoked");
        } else if (error instanceof SnapshotUnavailableError) {
          setData(null);
          setStatus("waiting");
        } else if (error instanceof UnsupportedSnapshotError) {
          terminal = true;
          setStatus("unsupported");
        } else if (error instanceof TemporaryApiError) {
          setStatus("offline");
        } else {
          setStatus("offline");
        }
      } finally {
        if (controller === requestController) {
          controller = null;
          busy = false;
          schedule();
        }
      }
    };

    const handleVisibility = () => {
      clearTimer();

      if (document.visibilityState === "hidden") {
        controller?.abort();
        controller = null;
        busy = false;
        return;
      }

      void runFetch();
    };

    refreshRef.current = () => {
      void runFetch();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    void runFetch();

    return () => {
      disposed = true;
      clearTimer();
      controller?.abort();
      controller = null;
      refreshRef.current = null;
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetcher, pairing.deviceId, pairing.viewSecret]);

  const refresh = useCallback(() => {
    refreshRef.current?.();
  }, []);

  return { status, data, refresh };
}
