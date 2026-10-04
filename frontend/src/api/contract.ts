import { z } from "zod";

const awareDateTime = z.string().datetime({ offset: true });
const nullableNumber = z.number().nullable();

const CollectorSchema = z
  .object({
    status: z.literal("monitoring"),
    last_collection_at: awareDateTime,
  })
  .strict();

const PortSchema = z
  .object({
    name: z.string(),
  })
  .strict();

const VesselSchema = z
  .object({
    name: z.string(),
    imo: z.string().nullable(),
    status: z.enum([
      "ATRACADO",
      "DESATRACANDO",
      "FUNDEADO",
      "ATRACANDO",
      "PREVISTO",
      "DESATRACADO",
    ]),
    section: z.enum(["ATRACADO", "FUNDEADO", "PREVISTO"]),
    berth: z.number().int().nullable(),
    side: z.string().nullable(),
    eta: z.string().nullable(),
    etb_ets: z.string().nullable(),
    pob: z.string().nullable(),
    flag: z.string().nullable(),
    origin_port: z.string().nullable(),
    irin: z.string().nullable(),
    agency: z.string().nullable(),
    tugs: z.string().nullable(),
  })
  .strict();

const WeatherSchema = z
  .object({
    consulted_at: awareDateTime.nullable(),
    observed_at: awareDateTime.nullable(),
    air_temperature_c: nullableNumber,
    humidity_pct: nullableNumber,
    weather_code: z.number().int().nullable(),
    wind_speed_kn: nullableNumber,
    wind_direction_deg: nullableNumber,
    wind_gust_kn: nullableNumber,
    visibility_m: nullableNumber,
    precipitation_mm: nullableNumber,
  })
  .strict();

const MarineSchema = z
  .object({
    consulted_at: awareDateTime.nullable(),
    observed_at: awareDateTime.nullable(),
    wave_height_m: nullableNumber,
    wave_direction_deg: nullableNumber,
    wave_period_s: nullableNumber,
    swell_height_m: nullableNumber,
    swell_direction_deg: nullableNumber,
    swell_period_s: nullableNumber,
    sea_temperature_c: nullableNumber,
    current_kn: nullableNumber,
    current_direction_deg: nullableNumber,
  })
  .strict();

const EmptyBlockSchema = z.object({}).strict();

const ManeuverSchema = z
  .object({
    id: z.string(),
    type: z.enum(["ATRACACAO", "DESATRACACAO"]),
    vessel_name: z.string(),
    berth: z.number().int().nullable(),
    pob: z.string().nullable(),
    status: z.enum(["ACTIVE", "COMPLETED"]),
    detected_at: awareDateTime,
    completed_at: awareDateTime.nullable(),
  })
  .strict();

const RecentManeuversSchema = z
  .object({
    active: z.array(ManeuverSchema),
    completed: z.array(ManeuverSchema),
  })
  .strict()
  .superRefine((value, ctx) => {
    value.active.forEach((maneuver, index) => {
      if (maneuver.status !== "ACTIVE" || maneuver.completed_at !== null) {
        ctx.addIssue({
          code: "custom",
          path: ["active", index],
          message: "Manobra ativa inválida.",
        });
      }
    });
    value.completed.forEach((maneuver, index) => {
      if (maneuver.status !== "COMPLETED" || maneuver.completed_at === null) {
        ctx.addIssue({
          code: "custom",
          path: ["completed", index],
          message: "Manobra concluída inválida.",
        });
      }
    });
  });

const MobileSnapshotV1Schema = z
  .object({
    schema_version: z.literal(1),
    boot_id: z.string().uuid(),
    sequence: z.number().int().positive(),
    generated_at: awareDateTime,
    collector: CollectorSchema,
    port: PortSchema,
    vessels: z.array(VesselSchema),
    weather: z.union([EmptyBlockSchema, WeatherSchema]),
    marine: z.union([EmptyBlockSchema, MarineSchema]),
    recent_maneuvers: RecentManeuversSchema,
  })
  .strict();

const UnavailableV2Schema = z
  .object({
    status: z.literal("unavailable"),
  })
  .strict();

const WebPilotAtmospherePrimaryV2Schema = z
  .object({
    status: z.enum(["fresh", "stale"]),
    source: z.literal("webpilot"),
    mode: z.literal("observed"),
    consulted_at: awareDateTime,
    observed_at: awareDateTime,
    wind_direction_deg: nullableNumber,
    wind_direction_cardinal: z.string().nullable(),
    wind_speed_current_kn: nullableNumber,
    wind_speed_mean_kn: nullableNumber,
    wind_speed_max_kn: nullableNumber,
    air_temperature_c: nullableNumber,
    apparent_temperature_c: nullableNumber,
    humidity_pct: nullableNumber,
    pressure_hpa: nullableNumber,
    pressure_6h_hpa: nullableNumber,
    precipitation_mm: nullableNumber,
  })
  .strict();

const OpenMeteoAtmospherePrimaryV2Schema = z
  .object({
    status: z.enum(["fresh", "stale"]),
    source: z.literal("open_meteo"),
    mode: z.literal("fallback"),
    consulted_at: awareDateTime.nullable(),
    observed_at: awareDateTime.nullable(),
    air_temperature_c: nullableNumber,
    humidity_pct: nullableNumber,
    weather_code: z.number().int().nullable(),
    wind_speed_kn: nullableNumber,
    wind_direction_deg: nullableNumber,
    wind_gust_kn: nullableNumber,
    visibility_m: nullableNumber,
    precipitation_mm: nullableNumber,
  })
  .strict();

const AtmospherePrimaryV2Schema = z.union([
  WebPilotAtmospherePrimaryV2Schema,
  OpenMeteoAtmospherePrimaryV2Schema,
  UnavailableV2Schema,
]);

const OpenMeteoComplementaryV2Schema = z
  .object({
    status: z.enum(["fresh", "stale"]),
    source: z.literal("open_meteo"),
    consulted_at: awareDateTime.nullable(),
    observed_at: awareDateTime.nullable(),
    weather_code: z.number().int().nullable(),
    visibility_m: nullableNumber,
  })
  .strict();

const AtmosphereComplementaryV2Schema = z.union([
  OpenMeteoComplementaryV2Schema,
  UnavailableV2Schema,
]);

const AtmosphereV2Schema = z
  .object({
    primary: AtmospherePrimaryV2Schema,
    complementary: AtmosphereComplementaryV2Schema,
  })
  .strict()
  .superRefine((value, ctx) => {
    const primary = value.primary;
    if ("source" in primary && primary.source === "open_meteo") {
      if (value.complementary.status !== "unavailable") {
        ctx.addIssue({
          code: "custom",
          path: ["complementary"],
          message: "Open-Meteo primário exige complementary unavailable.",
        });
      }
    }
    if (primary.status === "unavailable" && value.complementary.status !== "unavailable") {
      ctx.addIssue({
        code: "custom",
        path: ["complementary"],
        message: "Atmosfera indisponível exige complementary unavailable.",
      });
    }
  });

const OpenMeteoMarineV2Schema = z
  .object({
    status: z.enum(["fresh", "stale"]),
    source: z.literal("open_meteo"),
    consulted_at: awareDateTime.nullable(),
    observed_at: awareDateTime.nullable(),
    wave_height_m: nullableNumber,
    wave_direction_deg: nullableNumber,
    wave_period_s: nullableNumber,
    swell_height_m: nullableNumber,
    swell_direction_deg: nullableNumber,
    swell_period_s: nullableNumber,
    sea_temperature_c: nullableNumber,
    current_kn: nullableNumber,
    current_direction_deg: nullableNumber,
  })
  .strict();

const MarineV2Schema = z.union([
  OpenMeteoMarineV2Schema,
  UnavailableV2Schema,
]);

const MobileSnapshotV2Schema = z
  .object({
    schema_version: z.literal(2),
    boot_id: z.string().uuid(),
    sequence: z.number().int().positive(),
    generated_at: awareDateTime,
    collector: CollectorSchema,
    port: PortSchema,
    vessels: z.array(VesselSchema),
    atmosphere: AtmosphereV2Schema,
    marine: MarineV2Schema,
    recent_maneuvers: RecentManeuversSchema,
  })
  .strict();

const MobileSnapshotSchema = z.discriminatedUnion("schema_version", [
  MobileSnapshotV1Schema,
  MobileSnapshotV2Schema,
]);

const SnapshotMetaSchema = z
  .object({
    received_at: awareDateTime,
    age_seconds: z.number().int().nonnegative(),
    collector_online: z.boolean(),
    stale_after_seconds: z.number().int().nonnegative(),
  })
  .strict();

const SnapshotReadResponseSchema = z
  .object({
    snapshot: MobileSnapshotSchema,
    meta: SnapshotMetaSchema,
  })
  .strict();

const VesselPhotoResponseSchema = z
  .object({
    imo: z.string(),
    photo_url: z.string().url().nullable(),
    author: z.string().nullable(),
    license: z.string().nullable(),
    source_url: z.string().url().nullable(),
  })
  .strict();

export type VesselV1 = z.infer<typeof VesselSchema>;
export type ManeuverV1 = z.infer<typeof ManeuverSchema>;
export type MobileSnapshotV1 = z.infer<typeof MobileSnapshotV1Schema>;
export type MobileSnapshotV2 = z.infer<typeof MobileSnapshotV2Schema>;
export type MobileSnapshot = z.infer<typeof MobileSnapshotSchema>;
export type SnapshotReadResponse = z.infer<typeof SnapshotReadResponseSchema>;
export type VesselPhotoResponse = z.infer<typeof VesselPhotoResponseSchema>;

export function parseSnapshotReadResponse(input: unknown): SnapshotReadResponse {
  if (
    typeof input === "object" &&
    input !== null &&
    "snapshot" in input &&
    typeof input.snapshot === "object" &&
    input.snapshot !== null &&
    "schema_version" in input.snapshot &&
    input.snapshot.schema_version !== 1 &&
    input.snapshot.schema_version !== 2
  ) {
    throw new Error("Versão de snapshot não suportada.");
  }

  const parsed = SnapshotReadResponseSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de snapshot inválida.");
  }
  return parsed.data;
}

export function parseVesselPhotoResponse(input: unknown): VesselPhotoResponse {
  const parsed = VesselPhotoResponseSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de foto do navio inválida.");
  }
  return parsed.data;
}


const PobChangeSchema = z
  .object({
    from: z.string().nullable(),
    to: z.string().nullable(),
  })
  .strict();

const BerthChangeSchema = z
  .object({
    from: z.number().int().nullable(),
    to: z.number().int().nullable(),
  })
  .strict();

const ManeuverChangesSchema = z
  .object({
    pob: PobChangeSchema.optional(),
    berth: BerthChangeSchema.optional(),
  })
  .strict()
  .refine((value) => value.pob !== undefined || value.berth !== undefined, {
    message: "UPDATED exige ao menos uma alteração.",
  });

export const ManeuverEventSchema = z
  .object({
    event_id: z.string().uuid(),
    maneuver_id: z.string().uuid(),
    vessel_identity: z.string().min(1),
    vessel_imo: z.string().nullable(),
    vessel_name: z.string().min(1),
    maneuver_type: z.enum(["ATRACACAO", "DESATRACACAO"]),
    event_type: z.enum(["CONFIRMED", "UPDATED", "COMPLETED", "CANCELLED"]),
    berth: z.number().int().nullable(),
    pob: z.string().nullable(),
    occurred_at: awareDateTime,
    pob_at: awareDateTime.nullable().default(null),
    first_observed_at: awareDateTime.nullable().default(null),
    operational_at: awareDateTime.nullable().default(null),
    operational_marker: z.literal("ATRAC").nullable().default(null),
    changes: ManeuverChangesSchema.nullable(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.event_type === "UPDATED" && value.changes === null) {
      ctx.addIssue({
        code: "custom",
        path: ["changes"],
        message: "UPDATED exige changes.",
      });
    }
    if (value.event_type !== "UPDATED" && value.changes !== null) {
      ctx.addIssue({
        code: "custom",
        path: ["changes"],
        message: "Somente UPDATED aceita changes.",
      });
    }
    const hasOperationalAt = value.operational_at !== null;
    const hasOperationalMarker = value.operational_marker !== null;
    if (hasOperationalAt !== hasOperationalMarker) {
      ctx.addIssue({
        code: "custom",
        path: ["operational_at"],
        message: "Horário e marcador operacional devem ser informados juntos.",
      });
    }
    if (
      hasOperationalAt &&
      (value.event_type !== "COMPLETED" || value.maneuver_type !== "ATRACACAO")
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["operational_at"],
        message: "ATRAC operacional só é válido na conclusão de atracação.",
      });
    }
  });

export type ManeuverEventV1 = z.infer<typeof ManeuverEventSchema>;


const ManeuverEventFeedItemSchema = z
  .object({
    event_id: z.string().uuid(),
    maneuver_id: z.string().uuid(),
    vessel_identity: z.string().min(1),
    vessel_imo: z.string().nullable(),
    vessel_name: z.string().min(1),
    maneuver_type: z.enum(["ATRACACAO", "DESATRACACAO"]),
    event_type: z.enum(["CONFIRMED", "UPDATED", "COMPLETED", "CANCELLED"]),
    berth: z.number().int().nullable(),
    pob: z.string().nullable(),
    occurred_at: awareDateTime,
    pob_at: awareDateTime.nullable().default(null),
    first_observed_at: awareDateTime.nullable().default(null),
    operational_at: awareDateTime.nullable().default(null),
    operational_marker: z.literal("ATRAC").nullable().default(null),
    changes: ManeuverChangesSchema.nullable(),
    ingestion_id: z.number().int().positive(),
    ingested_at: awareDateTime,
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.event_type === "UPDATED" && value.changes === null) {
      ctx.addIssue({
        code: "custom",
        path: ["changes"],
        message: "UPDATED exige changes.",
      });
    }
    if (value.event_type !== "UPDATED" && value.changes !== null) {
      ctx.addIssue({
        code: "custom",
        path: ["changes"],
        message: "Somente UPDATED aceita changes.",
      });
    }
    const hasOperationalAt = value.operational_at !== null;
    const hasOperationalMarker = value.operational_marker !== null;
    if (hasOperationalAt !== hasOperationalMarker) {
      ctx.addIssue({
        code: "custom",
        path: ["operational_at"],
        message: "Horário e marcador operacional devem ser informados juntos.",
      });
    }
    if (
      hasOperationalAt &&
      (value.event_type !== "COMPLETED" || value.maneuver_type !== "ATRACACAO")
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["operational_at"],
        message: "ATRAC operacional só é válido na conclusão de atracação.",
      });
    }
  });

const ManeuverEventFeedResponseSchema = z
  .object({
    events: z.array(ManeuverEventFeedItemSchema),
    oldest_cursor: z.number().int().positive().nullable(),
    newest_cursor: z.number().int().positive().nullable(),
    has_more_before: z.boolean(),
  })
  .strict();

const ManeuverEventDetailResponseSchema = z
  .object({
    selected_event_id: z.string().uuid(),
    maneuver_id: z.string().uuid(),
    events: z.array(ManeuverEventFeedItemSchema),
  })
  .strict();

export type ManeuverEventFeedItem = z.infer<typeof ManeuverEventFeedItemSchema>;
export type ManeuverEventFeedResponse = z.infer<typeof ManeuverEventFeedResponseSchema>;
export type ManeuverEventDetailResponse = z.infer<typeof ManeuverEventDetailResponseSchema>;

export function parseManeuverEventFeedResponse(
  input: unknown,
): ManeuverEventFeedResponse {
  const parsed = ManeuverEventFeedResponseSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de eventos inválida.");
  }
  return parsed.data;
}

export function parseManeuverEventDetailResponse(
  input: unknown,
): ManeuverEventDetailResponse {
  const parsed = ManeuverEventDetailResponseSchema.safeParse(input);
  if (!parsed.success) {
    throw new Error("Resposta de detalhe de evento inválida.");
  }
  return parsed.data;
}
