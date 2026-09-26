import { useCallback, useEffect, useRef, useState } from "react";

export type PwaInstallState =
  | "installed"
  | "available"
  | "ios"
  | "unsupported";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform?: string }>;
};

function isStandalone(): boolean {
  const standaloneMedia =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(display-mode: standalone)").matches;
  const safariStandalone =
    Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
  return standaloneMedia || safariStandalone;
}

function isIosDevice(): boolean {
  const ua = navigator.userAgent;
  return (
    /iPhone|iPad|iPod/i.test(ua) ||
    (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1)
  );
}
function initialState(): PwaInstallState {
  if (isStandalone()) return "installed";
  if (isIosDevice()) return "ios";
  return "unsupported";
}

export function usePwaInstall() {
  const [state, setState] = useState<PwaInstallState>(() => initialState());
  const deferred = useRef<BeforeInstallPromptEvent | null>(null);
  const isIos = isIosDevice();

  useEffect(() => {
    const handlePrompt = (rawEvent: Event) => {
      const event = rawEvent as BeforeInstallPromptEvent;
      event.preventDefault();
      deferred.current = event;
      setState("available");
    };

    const handleInstalled = () => {
      deferred.current = null;
      setState("installed");
    };

    window.addEventListener("beforeinstallprompt", handlePrompt);
    window.addEventListener("appinstalled", handleInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", handlePrompt);
      window.removeEventListener("appinstalled", handleInstalled);
    };
  }, []);
  const install = useCallback(async () => {
    const event = deferred.current;
    if (!event) return;
    await event.prompt();
    await event.userChoice;
  }, []);

  return { state, install, isIos };
}
