import { z } from "zod";

import { ManeuverEventSchema } from "./contract";
import {
  AccessRevokedError,
  TemporaryApiError,
} from "./snapshotClient";

const awareDateTime = z.string().datetime({ offset: true });

const StringChangeSchema = z
  .object({
    from: z.string().nullable(),
    to: z.string().nullable(),
  })
  .strict();

const IntegerChangeSchema = z
  .object({
    from: z.number().int().nullable(),
    to: z.number().int().nullable(),
  })
  .strict();

const BooleanChangeSchema = z
  .object({
    from: z.boolean(),
    to: z.boolean(),
  })
  .strict();

export const VesselTrackingCurrentSchema = z
  .object({
    present: z.boolean(),
    status: z.string().nullable(),
    section: z.string().nullable(),
    berth: z.number().int().nullable(),
    side: z.string().nullable(),
    eta: z.string().nullable(),
    etb_ets: z.string().nullable(),
    pob: z.string().nullable(),
    pob_at: awareDateTime.nullable(),
  })
  .strict();

const TrackedVesselCurrentSchema = VesselTrackingCurrentSchema.extend({
  present: z.boolean().nullable(),
}).strict();

export const VesselTrackingChangesSchema = z
  .object({
    presence: BooleanChangeSchema.nullable().optional(),
    status: StringChangeSchema.nullable().optional(),
    section: StringChangeSchema.nullable().optional(),
    berth: IntegerChangeSchema.nullable().optional(),
    side: StringChangeSchema.nullable().optional(),
    eta: StringChangeSchema.nullable().optional(),
    etb_ets: StringChangeSchema.nullable().optional(),
    pob: StringChangeSchema.nullable().optional(),
  })
  .strict()
  .refine(
    (value) =>
      Object.values(value).some(
        (item) => item !== undefined && item !== null,
      ),
    { message: "VesselTrackingEvent exige ao menos uma alteração." },
  );

export const VesselTrackingEventSchema = z
  .object({
    event_id: z.string().uuid(),
    vessel_identity: z.string().min(1),
    vessel_imo: z.string().nullable(),
    vessel_name: z.string().min(1),
    occurred_at: awareDateTime,
    first_observed_at: awareDateTime.nullable(),
    maneuver_id: z.string().uuid().nullable(),
    changes: VesselTrackingChangesSchema,
    current: VesselTrackingCurrentSchema,
  })
  .strict();

export const TrackedVesselSchema = z
  .object({
    tracked_vessel_id: z.string().uuid(),
    vessel_identity: z.string().min(1),
    vessel_imo: z.string().nullable(),
    vessel_name: z.string().min(1),
    started_at: awareDateTime,
    active: z.boolean(),
    stopped_at: awareDateTime.nullable(),
    last_seen_at: awareDateTime.nullable(),
    current: TrackedVesselCurrentSchema.nullable(),
  })
  .strict();

const TimelineManeuverItemSchema = z
  .object({
    kind: z.literal("MANEUVER"),
    ingestion_id: z.number().int().positive(),
    ingested_at: awareDateTime,
    event: ManeuverEventSchema,
  })
  .strict();

const TimelineTrackingItemSchema = z
  .object({
    kind: z.literal("TRACKING"),
    ingestion_id: z.number().int().positive(),
    ingested_at: awareDateTime,
    event: VesselTrackingEventSchema,
  })
  .strict();

export const TrackedVesselTimelineSchema = z
  .object({
    tracked_vessel_id: z.string().uuid(),
    events: z.array(
      z.discriminatedUnion("kind", [
        TimelineManeuverItemSchema,
        TimelineTrackingItemSchema,
      ]),
    ),
  })
  .strict();

const TrackingForegroundFeedItemSchema = z
  .object({
    tracked_vessel_id: z.string().uuid(),
    ingestion_id: z.number().int().positive(),
    ingested_at: awareDateTime,
    event: VesselTrackingEventSchema,
  })
  .strict();

export const TrackingForegroundFeedSchema = z
  .object({
    events: z.array(TrackingForegroundFeedItemSchema),
    newest_cursor: z.number().int().nonnegative().nullable(),
  })
  .strict();

export type TrackedVessel = z.infer<typeof TrackedVesselSchema>;
export type VesselTrackingEvent = z.infer<typeof VesselTrackingEventSchema>;
export type TrackedVesselTimeline = z.infer<typeof TrackedVesselTimelineSchema>;
export type TrackingForegroundFeedItem = z.infer<
  typeof TrackingForegroundFeedItemSchema
>;
export type TrackingForegroundFeedResponse = z.infer<
  typeof TrackingForegroundFeedSchema
>;

export type TrackingTarget = {
  vessel_identity: string;
  vessel_imo: string | null;
  vessel_name: string;
};

export type TrackingEventQuery = {
  after?: number;
  limit?: number;
};

export function parseTrackedVessel(input: unknown): TrackedVessel {
  const parsed = TrackedVesselSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de acompanhamento inválida.");
  }
  return parsed.data;
}

export function parseTrackedVesselTimeline(
  input: unknown,
): TrackedVesselTimeline {
  const parsed = TrackedVesselTimelineSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de timeline de acompanhamento inválida.");
  }
  return parsed.data;
}

function parseTrackedVessels(input: unknown): TrackedVessel[] {
  const parsed = z.array(TrackedVesselSchema).safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de acompanhamentos inválida.");
  }
  return parsed.data;
}

function parseTrackingFeed(
  input: unknown,
): TrackingForegroundFeedResponse {
  const parsed = TrackingForegroundFeedSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta do feed de acompanhamento inválida.");
  }
  return parsed.data;
}

async function requestJson(
  url: string,
  init?: RequestInit,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
      ...init,
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
  if (response.status === 401) throw new AccessRevokedError();
  if (!response.ok) throw new TemporaryApiError();
  try {
    return await response.json();
  } catch {
    throw new TemporaryApiError();
  }
}

export async function listTrackedVessels(
  signal?: AbortSignal,
): Promise<TrackedVessel[]> {
  try {
    return parseTrackedVessels(
      await requestJson("/api/v1/mobile/tracked-vessels", { signal }),
    );
  } catch (error) {
    if (
      error instanceof AccessRevokedError ||
      error instanceof TemporaryApiError ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }
}

export async function startTracking(
  target: TrackingTarget,
  signal?: AbortSignal,
): Promise<TrackedVessel> {
  try {
    return parseTrackedVessel(
      await requestJson("/api/v1/mobile/tracked-vessels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(target),
        signal,
      }),
    );
  } catch (error) {
    if (
      error instanceof AccessRevokedError ||
      error instanceof TemporaryApiError ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }
}

export async function stopTracking(
  trackedVesselId: string,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(
      `/api/v1/mobile/tracked-vessels/${encodeURIComponent(trackedVesselId)}`,
      {
        method: "DELETE",
        cache: "no-store",
        credentials: "same-origin",
        signal,
      },
    );
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new TemporaryApiError();
  }
  if (response.status === 401) throw new AccessRevokedError();
  if (!response.ok) throw new TemporaryApiError();
}

export async function getTrackedVesselTimeline(
  trackedVesselId: string,
  signal?: AbortSignal,
): Promise<TrackedVesselTimeline> {
  try {
    return parseTrackedVesselTimeline(
      await requestJson(
        `/api/v1/mobile/tracked-vessels/${encodeURIComponent(trackedVesselId)}/events`,
        { signal },
      ),
    );
  } catch (error) {
    if (
      error instanceof AccessRevokedError ||
      error instanceof TemporaryApiError ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }
}

export async function getTrackingEvents(
  query: TrackingEventQuery,
  signal?: AbortSignal,
): Promise<TrackingForegroundFeedResponse> {
  const params = new URLSearchParams();
  if (query.after !== undefined) params.set("after", String(query.after));
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  const suffix = params.size ? `?${params.toString()}` : "";
  try {
    return parseTrackingFeed(
      await requestJson(
        `/api/v1/mobile/tracked-vessels/events${suffix}`,
        { signal },
      ),
    );
  } catch (error) {
    if (
      error instanceof AccessRevokedError ||
      error instanceof TemporaryApiError ||
      (error instanceof Error && error.name === "AbortError")
    ) {
      throw error;
    }
    throw new TemporaryApiError();
  }
}

export function normalizeTrackingName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toUpperCase();
}

export function trackingIdentity(
  vesselImo: string | null,
  vesselName: string,
): string {
  return vesselImo
    ? `IMO:${vesselImo.trim()}`
    : `NAME:${normalizeTrackingName(vesselName)}`;
}

export function trackedVesselMatches(
  tracked: TrackedVessel,
  target: TrackingTarget,
): boolean {
  if (tracked.vessel_identity === target.vessel_identity) return true;
  if (target.vessel_imo) {
    if (tracked.vessel_imo === target.vessel_imo) return true;
    return (
      tracked.vessel_imo === null &&
      normalizeTrackingName(tracked.vessel_name) ===
        normalizeTrackingName(target.vessel_name)
    );
  }
  return (
    tracked.vessel_imo === null &&
    normalizeTrackingName(tracked.vessel_name) ===
      normalizeTrackingName(target.vessel_name)
  );
}
