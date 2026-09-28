import { expect, test } from "vitest";
import {
  API_RUNTIME_CACHING,
  PWA_INJECT_MANIFEST_CONFIG,
} from "./pwaConfig";

test("pwa_uses_inject_manifest_with_custom_service_worker", () => {
  expect(PWA_INJECT_MANIFEST_CONFIG).toEqual({
    strategies: "injectManifest",
    srcDir: "src",
    filename: "sw.ts",
    registerType: "autoUpdate",
  });
});

test("api_runtime_rule_is_network_only", () => {
  expect(API_RUNTIME_CACHING.handler).toBe("NetworkOnly");
  expect(API_RUNTIME_CACHING.urlPattern.test("https://alertam.example/api/v1/devices/x/snapshot")).toBe(true);
  expect(API_RUNTIME_CACHING.urlPattern.test("https://alertam.example/assets/app.js")).toBe(false);
});
