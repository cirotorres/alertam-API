import type { MobileSnapshot, VesselV1 } from "../../api/contract";
import { vesselByBerth } from "../vessels/projections";

export const BERTH_POSITIONS: Record<number, { xPct: number; yPct: number }> = {
  1: { xPct: 37, yPct: 75 },
  2: { xPct: 43, yPct: 69 },
  3: { xPct: 49, yPct: 64 },
  4: { xPct: 55, yPct: 59 },
  5: { xPct: 62, yPct: 54 },
  6: { xPct: 53, yPct: 44 },
  7: { xPct: 45, yPct: 36 },
  8: { xPct: 38, yPct: 28 },
  9: { xPct: 31, yPct: 20 },
  10: { xPct: 24, yPct: 12 },
};

export type MapVessel = {
  berth: number;
  vessel: VesselV1;
  sprite: string;
  position: { xPct: number; yPct: number };
  moving: boolean;
};
const SPRITES: Partial<Record<VesselV1["status"], string>> = {
  ATRACADO: "/assets/navio.png",
  ATRACANDO: "/assets/navio_green.png",
  DESATRACANDO: "/assets/navio_red.png",
};

export function selectMapVessels(snapshot: MobileSnapshot): MapVessel[] {
  const result: MapVessel[] = [];

  for (const berth of Object.keys(BERTH_POSITIONS).map(Number)) {
    const vessel = vesselByBerth(snapshot, berth);
    if (!vessel) continue;
    const sprite = SPRITES[vessel.status];
    if (!sprite) continue;
    result.push({
      berth,
      vessel,
      sprite,
      position: BERTH_POSITIONS[berth],
      moving: vessel.status === "ATRACANDO" || vessel.status === "DESATRACANDO",
    });
  }

  return result;
}
