import {
  parseManeuverEventDetailResponse,
  parseManeuverEventFeedResponse,
  type ManeuverEventDetailResponse,
  type ManeuverEventFeedResponse,
} from "./contract";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "./snapshotClient";

export type ManeuverEventQuery = {
  after?: number;
  before?: number;
  limit?: number;
};

export async function getManeuverEvents(
  query: ManeuverEventQuery,
  signal?: AbortSignal,
): Promise<ManeuverEventFeedResponse> {
  const params = new URLSearchParams();
  if (query.after !== undefined) params.set("after", String(query.after));
  if (query.before !== undefined) params.set("before", String(query.before));
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";

  let response: Response;
  try {
    response = await fetch(`/api/v1/mobile/maneuver-events${suffix}`, {
      cache: "no-store",
      credentials: "same-origin",
      signal,
    });
  } catch (error) {
    if (
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }

  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (!response.ok) {
    throw new TemporaryApiError();
  }

  let body: unknown;
  try {
    body = await response.json();
    return parseManeuverEventFeedResponse(body);
  } catch {
    throw new TemporaryApiError();
  }
}


export class ManeuverEventDetailNotFoundError extends Error {
  constructor() {
    super("Este alerta não está mais disponível no histórico recente.");
    this.name = "ManeuverEventDetailNotFoundError";
  }
}

export async function getManeuverEventDetail(
  eventId: string,
  signal?: AbortSignal,
): Promise<ManeuverEventDetailResponse> {
  let response: Response;
  try {
    response = await fetch(
      `/api/v1/mobile/events/${encodeURIComponent(eventId)}/detail`,
      {
        cache: "no-store",
        credentials: "same-origin",
        signal,
      },
    );
  } catch (error) {
    if (
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }

  if (response.status === 401) {
    throw new AccessRevokedError();
  }
  if (response.status === 404) {
    throw new ManeuverEventDetailNotFoundError();
  }
  if (!response.ok) {
    throw new TemporaryApiError();
  }

  try {
    return parseManeuverEventDetailResponse(await response.json());
  } catch {
    throw new TemporaryApiError();
  }
}
