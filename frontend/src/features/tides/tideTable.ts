import tideDataset from "../../data/tides/pecem-2026.json";

export type TideEvent = {
  time: string;
  height_m: number;
};

export type TideDay = {
  date: string;
  events: TideEvent[];
  available: boolean;
};

export type TideView = {
  today: TideDay;
  tomorrow: TideDay;
  nextEvent: { date: string; event: TideEvent } | null;
};

type TideDataset = {
  schema_version: number;
  station: string;
  year: number;
  timezone_offset: string;
  source: {
    publisher: string;
    chart: string;
    mean_level_m: number;
    source_pdf_sha256: string;
  };
  days: Record<string, TideEvent[]>;
};

const DATASET = tideDataset as TideDataset;
const PECEM_OFFSET_MS = -3 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

function dateKeyFromShiftedUtc(value: Date): string {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, "0");
  const day = String(value.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dayFromKey(date: string): TideDay {
  const events = DATASET.days[date];
  if (!events) {
    return { date, events: [], available: false };
  }
  return { date, events: events.map((event) => ({ ...event })), available: true };
}

function minutes(value: string): number {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

export function selectTideView(now: Date): TideView {
  const pecemClock = new Date(now.getTime() + PECEM_OFFSET_MS);
  const todayKey = dateKeyFromShiftedUtc(pecemClock);

  const todayMidnightUtc = Date.UTC(
    pecemClock.getUTCFullYear(),
    pecemClock.getUTCMonth(),
    pecemClock.getUTCDate(),
  );
  const tomorrowKey = dateKeyFromShiftedUtc(new Date(todayMidnightUtc + DAY_MS));

  const today = dayFromKey(todayKey);
  const tomorrow = dayFromKey(tomorrowKey);
  const currentMinutes = pecemClock.getUTCHours() * 60 + pecemClock.getUTCMinutes();

  let nextEvent: TideView["nextEvent"] = null;
  if (today.available) {
    const event = today.events.find((candidate) => minutes(candidate.time) >= currentMinutes);
    if (event) nextEvent = { date: today.date, event };
  }
  if (!nextEvent && tomorrow.available && tomorrow.events.length > 0) {
    nextEvent = { date: tomorrow.date, event: tomorrow.events[0] };
  }

  return { today, tomorrow, nextEvent };
}

export const tideTableMetadata = {
  station: DATASET.station,
  year: DATASET.year,
  publisher: DATASET.source.publisher,
  chart: DATASET.source.chart,
  timezoneOffset: DATASET.timezone_offset,
} as const;
