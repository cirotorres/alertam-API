import { useCallback, useEffect, useRef, useState } from "react";

import {
  getManeuverEvents,
  type ManeuverEventQuery,
} from "../../api/maneuverEventClient";
import type {
  ManeuverEventFeedItem,
  ManeuverEventFeedResponse,
} from "../../api/contract";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";


const POLL_INTERVAL_MS = 30_000;
const PAGE_LIMIT = 50;

export type EventStatus =
  | "idle"
  | "loading"
  | "online"
  | "offline"
  | "revoked";

export type EventFetcher = (
  query: ManeuverEventQuery,
  signal?: AbortSignal,
) => Promise<ManeuverEventFeedResponse>;

export type EventState = {
  events: ManeuverEventFeedItem[];
  status: EventStatus;
  newEvent: ManeuverEventFeedItem | null;
  hasMore: boolean;
  loadOlder: () => Promise<boolean>;
};

export function useEventPolling(
  enabled: boolean,
  fetcher: EventFetcher = getManeuverEvents,
  onAccessRevoked?: () => void,
): EventState {
  const [events, setEvents] = useState<ManeuverEventFeedItem[]>([]);
  const [status, setStatus] = useState<EventStatus>("idle");
  const [newEvent, setNewEvent] = useState<ManeuverEventFeedItem | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const eventsRef = useRef<ManeuverEventFeedItem[]>([]);
  const hasMoreRef = useRef(false);
  const loadOlderRef = useRef<() => Promise<boolean>>(async () => false);

  useEffect(() => {
    eventsRef.current = [];
    hasMoreRef.current = false;
    setEvents([]);
    setNewEvent(null);
    setHasMore(false);

    if (!enabled) {
      setStatus("idle");
      loadOlderRef.current = async () => false;
      return;
    }

    setStatus("loading");
    let disposed = false;
    let terminal = false;
    let busy = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;
    let newestCursor: number | null = null;
    let oldestCursor: number | null = null;

    const clearTimer = () => {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const mergeEvents = (
      incoming: ManeuverEventFeedItem[],
      announce: boolean,
    ) => {
      const map = new Map(
        eventsRef.current.map((item) => [item.event_id, item] as const),
      );
      const added: ManeuverEventFeedItem[] = [];
      for (const item of incoming) {
        if (!map.has(item.event_id)) {
          map.set(item.event_id, item);
          added.push(item);
        }
      }
      if (added.length === 0) return;

      const next = Array.from(map.values()).sort(
        (a, b) => a.ingestion_id - b.ingestion_id,
      );
      eventsRef.current = next;
      oldestCursor = next[0]?.ingestion_id ?? null;
      newestCursor = next.at(-1)?.ingestion_id ?? null;
      setEvents(next);
      if (announce) {
        added.sort((a, b) => a.ingestion_id - b.ingestion_id);
        setNewEvent(added.at(-1) ?? null);
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
      timer = setTimeout(() => {
        void fetchNew(false);
      }, POLL_INTERVAL_MS);
    };

    const fetchNew = async (initial: boolean) => {
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
        let query: ManeuverEventQuery = initial
          ? { limit: PAGE_LIMIT }
          : {
              after: newestCursor ?? undefined,
              limit: PAGE_LIMIT,
            };
        let firstPage = true;

        while (!disposed && !requestController.signal.aborted) {
          const page = await fetcher(query, requestController.signal);
          if (disposed || requestController.signal.aborted) return;

          if (initial && firstPage) {
            hasMoreRef.current = page.has_more_before;
            setHasMore(page.has_more_before);
          }
          mergeEvents(page.events, !initial);

          if (
            initial ||
            page.events.length < PAGE_LIMIT ||
            page.newest_cursor === null
          ) {
            break;
          }
          query = {
            after: page.newest_cursor,
            limit: PAGE_LIMIT,
          };
          firstPage = false;
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

    loadOlderRef.current = async () => {
      if (
        disposed ||
        terminal ||
        busy ||
        oldestCursor === null ||
        !hasMoreRef.current
      ) {
        return false;
      }
      busy = true;
      clearTimer();
      const requestController = new AbortController();
      controller = requestController;
      try {
        const page = await fetcher(
          { before: oldestCursor, limit: PAGE_LIMIT },
          requestController.signal,
        );
        if (disposed || requestController.signal.aborted) return false;
        mergeEvents(page.events, false);
        hasMoreRef.current = page.has_more_before;
        setHasMore(page.has_more_before);
        setStatus("online");
        return page.events.length > 0;
      } catch (error) {
        if (error instanceof AccessRevokedError) {
          terminal = true;
          setStatus("revoked");
          onAccessRevoked?.();
        } else if (
          !requestController.signal.aborted &&
          !(error instanceof Error && error.name === "AbortError")
        ) {
          setStatus("offline");
        }
        return false;
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
      void fetchNew(false);
    };

    document.addEventListener("visibilitychange", handleVisibility);
    void fetchNew(true);

    return () => {
      disposed = true;
      clearTimer();
      controller?.abort();
      controller = null;
      loadOlderRef.current = async () => false;
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [enabled, fetcher, onAccessRevoked]);

  const loadOlder = useCallback(() => loadOlderRef.current(), []);

  return {
    events,
    status,
    newEvent,
    hasMore,
    loadOlder,
  };
}
