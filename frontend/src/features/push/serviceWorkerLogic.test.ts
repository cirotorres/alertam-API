import { expect, test, vi } from "vitest";

import {
  buildNotificationOptions,
  handleNotificationClick,
  parsePushPayload,
} from "./serviceWorkerLogic";


const PAYLOAD = {
  event_id: "70000000-0000-4000-8000-000000000001",
  title: "Atracação confirmada",
  body: "NAVIO A · Berço 4",
  url: "/alertas?event=70000000-0000-4000-8000-000000000001",
};


test("invalid_push_payload_is_ignored_without_invented_content", () => {
  expect(parsePushPayload(null)).toBeNull();
  expect(parsePushPayload({ title: "sem evento" })).toBeNull();
  expect(parsePushPayload({
    ...PAYLOAD,
    url: "https://evil.example/alertas",
  })).toBeNull();
});


test("same_event_id_uses_same_notification_tag", () => {
  const parsed = parsePushPayload(PAYLOAD);
  expect(parsed).toEqual(PAYLOAD);

  const first = buildNotificationOptions(parsed!);
  const second = buildNotificationOptions(parsed!);
  expect(first).toMatchObject({
    body: PAYLOAD.body,
    tag: PAYLOAD.event_id,
    renotify: false,
    data: {
      url: PAYLOAD.url,
      event_id: PAYLOAD.event_id,
    },
  });
  expect(second.tag).toBe(first.tag);
});


test("notification_click_prefers_existing_same_origin_window", async () => {
  const existing = {
    url: "https://alertam.example/mapa",
    navigate: vi.fn().mockResolvedValue(undefined),
    focus: vi.fn().mockResolvedValue(undefined),
  };
  const clientsApi = {
    matchAll: vi.fn().mockResolvedValue([existing]),
    openWindow: vi.fn().mockResolvedValue(undefined),
  };

  await handleNotificationClick(
    clientsApi,
    PAYLOAD.url,
    "https://alertam.example",
  );

  expect(existing.navigate).toHaveBeenCalledWith(
    "https://alertam.example" + PAYLOAD.url,
  );
  expect(existing.focus).toHaveBeenCalledTimes(1);
  expect(clientsApi.openWindow).not.toHaveBeenCalled();
});


test("notification_click_opens_window_when_none_exists", async () => {
  const clientsApi = {
    matchAll: vi.fn().mockResolvedValue([]),
    openWindow: vi.fn().mockResolvedValue(undefined),
  };

  await handleNotificationClick(
    clientsApi,
    PAYLOAD.url,
    "https://alertam.example",
  );

  expect(clientsApi.openWindow).toHaveBeenCalledWith(
    "https://alertam.example" + PAYLOAD.url,
  );
});
