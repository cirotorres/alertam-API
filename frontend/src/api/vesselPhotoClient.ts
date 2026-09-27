import type { Pairing } from "../features/pairing/pairing";
import {
  parseVesselPhotoResponse,
  type VesselPhotoResponse,
} from "./contract";
import { AccessRevokedError, TemporaryApiError } from "./snapshotClient";

export async function getVesselPhoto(
  pairing: Pairing,
  imo: string,
  signal?: AbortSignal,
): Promise<VesselPhotoResponse> {
  let response: Response;
  try {
    response = await fetch(
      `/api/v1/devices/${encodeURIComponent(pairing.deviceId)}/vessels/${encodeURIComponent(imo)}/photo`,
      {
        cache: "no-store",
        credentials: "same-origin",
        headers: pairing.viewSecret
          ? { Authorization: `Bearer ${pairing.viewSecret}` }
          : undefined,
        signal,
      },
    );
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new TemporaryApiError();
  }

  if (response.status === 401) throw new AccessRevokedError();
  if (!response.ok) throw new TemporaryApiError();

  try {
    return parseVesselPhotoResponse(await response.json());
  } catch {
    throw new TemporaryApiError();
  }
}
