import { useEffect } from "react";

import { touchPushForeground } from "../../api/pushClient";
import { AccessRevokedError } from "../../api/snapshotClient";
import { loadInstallationId } from "./installationId";


const HEARTBEAT_INTERVAL_MS = 30_000;

export type ForegroundHeartbeatSender = (
  installationId: string,
) => Promise<unknown>;


export function useForegroundHeartbeat(
  enabled: boolean,
  heartbeat: ForegroundHeartbeatSender = touchPushForeground,
  onAccessRevoked?: () => void,
): void {
  useEffect(() => {
    if (!enabled) {
      return;
    }

    const installationId = loadInstallationId();
    if (!installationId) {
      return;
    }

    let timer: number | null = null;

    const stopTimer = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const send = () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      void heartbeat(installationId).catch((error: unknown) => {
        if (error instanceof AccessRevokedError) {
          onAccessRevoked?.();
        }
      });
    };

    const startVisibleCycle = () => {
      stopTimer();
      if (document.visibilityState !== "visible") {
        return;
      }
      send();
      timer = window.setInterval(send, HEARTBEAT_INTERVAL_MS);
    };

    const handleVisibility = () => {
      startVisibleCycle();
    };

    document.addEventListener(
      "visibilitychange",
      handleVisibility,
    );
    startVisibleCycle();

    return () => {
      stopTimer();
      document.removeEventListener(
        "visibilitychange",
        handleVisibility,
      );
    };
  }, [enabled, heartbeat, onAccessRevoked]);
}
