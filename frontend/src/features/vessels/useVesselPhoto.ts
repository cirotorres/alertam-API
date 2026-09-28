import { useEffect, useState } from "react";

import { getVesselPhoto } from "../../api/vesselPhotoClient";
import type { VesselPhotoResponse, VesselV1 } from "../../api/contract";
import type { Pairing } from "../pairing/pairing";
import {
  readVesselPhotoCache,
  writeVesselPhotoCache,
} from "./vesselPhotoCache";

type UseVesselPhotoOptions = {
  pairing: Pairing;
  vessel: VesselV1 | null;
  open: boolean;
  demoMode: boolean;
};

export function useVesselPhoto({
  pairing,
  vessel,
  open,
  demoMode,
}: UseVesselPhotoOptions) {
  const [photo, setPhoto] = useState<VesselPhotoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<"temporary" | null>(null);

  useEffect(() => {
    if (!open) return;
    const imo = vessel?.imo;
    if (!imo || demoMode) {
      setPhoto(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cached = readVesselPhotoCache(imo);
    if (cached) {
      setPhoto(cached);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setPhoto(null);
    setLoading(true);
    setError(null);
    getVesselPhoto(pairing, imo, controller.signal)
      .then((result) => {
        writeVesselPhotoCache(result);
        setPhoto(result);
        setError(null);
      })
      .catch((requestError) => {
        if (
          !(
            requestError instanceof Error &&
            requestError.name === "AbortError"
          )
        ) {
          setPhoto(null);
          setError("temporary");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [demoMode, open, pairing.deviceId, pairing.viewSecret, vessel?.imo]);

  return { photo, loading, error };
}
