import { useEffect, useState } from "react";

import {
  getTrackingEvents,
  type TrackingEventQuery,
  type TrackingForegroundFeedItem,
  type TrackingForegroundFeedResponse,
} from "../../api/trackingClient";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";

const POLL_INTERVAL_MS = 30_000;
const PAGE_LIMIT = 100;

export type TrackingPollingStatus =
  | "idle"
  | "loading"
  | "online"
  | "offline"
  | "revoked";

export type TrackingEventFetcher = (
  query: TrackingEventQuery,
  signal?: AbortSignal,
) => Promise<TrackingForegroundFeedResponse>;

export type TrackingPollingState = {
  status: TrackingPollingStatus;
  newTrackingEvent: TrackingForegroundFeedItem | null;
};

export function useTrackingPolling(
  enabled: boolean,
  fetcher: TrackingEventFetcher = getTrackingEvents,
  onAccessRevoked?: () => void,
): TrackingPollingState {
  const [status, setStatus] = useState<TrackingPollingStatus>("idle");
  const [newTrackingEvent, setNewTrackingEvent] =
    useState<TrackingForegroundFeedItem | null>(null);

  useEffect(() => {
    setNewTrackingEvent(null);
    if (!enabled) {
      setStatus("idle");
      return;
    }

    setStatus("loading");
    let disposed = false;
    let terminal = false;
    let busy = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;
    let cursor = 0;

    const clearTimer = () => {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const schedule = () => {
      clearTimer();
      if (
        disposed ||
        terminal ||
        document.visibilityState !== "visible"
      ) {
        return;
      }
      timer = setTimeout(() => void poll(false), POLL_INTERVAL_MS);
    };

    const poll = async (initial: boolean) => {
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
        let query: TrackingEventQuery = initial
          ? { limit: PAGE_LIMIT }
          : { after: cursor, limit: PAGE_LIMIT };
        const announced: TrackingForegroundFeedItem[] = [];

        while (!disposed && !requestController.signal.aborted) {
          const page = await fetcher(query, requestController.signal);
          if (disposed || requestController.signal.aborted) return;

          const nextCursor = page.newest_cursor ?? cursor;
          if (!initial) announced.push(...page.events);
          cursor = nextCursor;

          if (
            initial ||
            page.events.length < PAGE_LIMIT ||
            page.newest_cursor === null
          ) {
            break;
          }
          query = { after: cursor, limit: PAGE_LIMIT };
        }

        if (!initial && announced.length > 0) {
          announced.sort((a, b) => a.ingestion_id - b.ingestion_id);
          setNewTrackingEvent(announced.at(-1) ?? null);
        }
        setStatus("online");
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
          setStatus("revoked");
          onAccessRevoked?.();
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
      void poll(false);
    };

    document.addEventListener("visibilitychange", handleVisibility);
    void poll(true);

    return () => {
      disposed = true;
      clearTimer();
      controller?.abort();
      controller = null;
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled, fetcher, onAccessRevoked]);

  return { status, newTrackingEvent };
}
