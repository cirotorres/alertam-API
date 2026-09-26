import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { usePwaInstall } from "./usePwaInstall";

const originalUserAgent = navigator.userAgent;
const originalTouchPoints = navigator.maxTouchPoints;

function mockStandalone(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
    matches,
    media: "(display-mode: standalone)",
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: globalThis.matchMedia,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  Object.defineProperty(navigator, "userAgent", { configurable: true, value: originalUserAgent });
  Object.defineProperty(navigator, "maxTouchPoints", { configurable: true, value: originalTouchPoints });
});
test("detects_standalone_as_installed", () => {
  mockStandalone(true);
  const { result } = renderHook(() => usePwaInstall());
  expect(result.current.state).toBe("installed");
});

test("captures_beforeinstallprompt_and_installs_after_browser_event", async () => {
  mockStandalone(false);
  const prompt = vi.fn().mockResolvedValue(undefined);
  const event = new Event("beforeinstallprompt") as Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{ outcome: "accepted" }>;
  };
  event.prompt = prompt;
  event.userChoice = Promise.resolve({ outcome: "accepted" });

  const { result } = renderHook(() => usePwaInstall());
  act(() => window.dispatchEvent(event));
  expect(result.current.state).toBe("available");

  await act(async () => {
    await result.current.install();
  });
  expect(prompt).toHaveBeenCalledTimes(1);

  act(() => window.dispatchEvent(new Event("appinstalled")));
  expect(result.current.state).toBe("installed");
});
test("detects_ios_without_native_install_prompt", () => {
  mockStandalone(false);
  Object.defineProperty(navigator, "userAgent", {
    configurable: true,
    value: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
  });
  const { result } = renderHook(() => usePwaInstall());

  expect(result.current.state).toBe("ios");
  expect(result.current.isIos).toBe(true);
});

test("reports_unsupported_browser_when_no_install_path_exists", () => {
  mockStandalone(false);
  const { result } = renderHook(() => usePwaInstall());
  expect(result.current.state).toBe("unsupported");
});
