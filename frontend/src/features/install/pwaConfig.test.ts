import { expect, test } from "vitest";
import { API_RUNTIME_CACHING } from "./pwaConfig";

test("api_runtime_rule_is_network_only", () => {
  expect(API_RUNTIME_CACHING.handler).toBe("NetworkOnly");
  expect(API_RUNTIME_CACHING.urlPattern.test("https://alertam.example/api/v1/devices/x/snapshot")).toBe(true);
  expect(API_RUNTIME_CACHING.urlPattern.test("https://alertam.example/assets/app.js")).toBe(false);
});
