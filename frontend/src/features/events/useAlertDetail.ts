import { useCallback, useEffect, useState } from "react";

import type { ManeuverEventDetailResponse } from "../../api/contract";
import {
  getManeuverEventDetail,
  ManeuverEventDetailNotFoundError,
} from "../../api/maneuverEventClient";
import {
  AccessRevokedError,
} from "../../api/snapshotClient";


export type AlertDetailStatus =
  | "idle"
  | "loading"
  | "ready"
  | "not-found"
  | "error";

export type AlertDetailFetcher = (
  eventId: string,
  signal?: AbortSignal,
) => Promise<ManeuverEventDetailResponse>;

export type AlertDetailState = {
  status: AlertDetailStatus;
  detail: ManeuverEventDetailResponse | null;
  retry: () => void;
};

export function useAlertDetail(
  eventId: string | null,
  fetcher: AlertDetailFetcher = getManeuverEventDetail,
  onAccessRevoked?: () => void,
): AlertDetailState {
  const [status, setStatus] = useState<AlertDetailStatus>("idle");
  const [detail, setDetail] = useState<ManeuverEventDetailResponse | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (eventId === null) {
      setStatus("idle");
      setDetail(null);
      return;
    }

    const controller = new AbortController();
    let disposed = false;

    setStatus("loading");
    setDetail(null);

    void fetcher(eventId, controller.signal)
      .then((response) => {
        if (disposed || controller.signal.aborted) return;
        setDetail(response);
        setStatus("ready");
      })
      .catch((error) => {
        if (
          disposed ||
          controller.signal.aborted ||
          (error instanceof Error && error.name === "AbortError")
        ) {
          return;
        }
        if (error instanceof ManeuverEventDetailNotFoundError) {
          setStatus("not-found");
          return;
        }
        if (error instanceof AccessRevokedError) {
          onAccessRevoked?.();
        }
        setStatus("error");
      });

    return () => {
      disposed = true;
      controller.abort();
    };
  }, [eventId, fetcher, onAccessRevoked, revision]);

  const retry = useCallback(() => {
    if (eventId === null) return;
    setRevision((value) => value + 1);
  }, [eventId]);

  return { status, detail, retry };
}
