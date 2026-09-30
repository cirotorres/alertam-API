import { useEffect } from "react";

import { AccessRevokedError } from "../../api/snapshotClient";
import { detectDevicePlatform, type DevicePlatform } from "./devicePlatform";
import { touchMobileSession } from "./mobileSessionClient";

const MOBILE_SESSION_HEARTBEAT_INTERVAL_MS = 5 * 60_000;

export type MobileSessionHeartbeatSender = (
  platform: DevicePlatform,
) => Promise<void>;

export function useMobileSessionHeartbeat(
  enabled: boolean,
  heartbeat: MobileSessionHeartbeatSender = touchMobileSession,
  onAccessRevoked?: () => void,
  platformProvider: () => DevicePlatform = detectDevicePlatform,
): void {
  useEffect(() => {
    if (!enabled) {
      return;
    }

    let timer: number | null = null;
    let busy = false;
    let stopped = false;
    let revokedReported = false;

    const stopTimer = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const send = () => {
      if (
        stopped ||
        busy ||
        document.visibilityState !== "visible"
      ) {
        return;
      }

      busy = true;
      void heartbeat(platformProvider())
        .catch((error: unknown) => {
          if (
            error instanceof AccessRevokedError &&
            !revokedReported
          ) {
            revokedReported = true;
            stopped = true;
            stopTimer();
            onAccessRevoked?.();
          }
        })
        .finally(() => {
          busy = false;
        });
    };

    const startVisibleCycle = () => {
      stopTimer();
      if (
        stopped ||
        document.visibilityState !== "visible"
      ) {
        return;
      }
      send();
      timer = window.setInterval(
        send,
        MOBILE_SESSION_HEARTBEAT_INTERVAL_MS,
      );
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
      stopped = true;
      stopTimer();
      document.removeEventListener(
        "visibilitychange",
        handleVisibility,
      );
    };
  }, [enabled, heartbeat, onAccessRevoked, platformProvider]);
}
