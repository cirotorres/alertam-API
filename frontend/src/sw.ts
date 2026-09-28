/// <reference lib="webworker" />

import { clientsClaim } from "workbox-core";
import {
  cleanupOutdatedCaches,
  precacheAndRoute,
} from "workbox-precaching";
import { registerRoute } from "workbox-routing";
import { NetworkOnly } from "workbox-strategies";

import { API_RUNTIME_CACHING } from "./features/install/pwaConfig";
import {
  buildNotificationOptions,
  handleNotificationClick,
  parsePushPayload,
  type WindowClientsLike,
} from "./features/push/serviceWorkerLogic";


declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<
    string | { url: string; revision?: string | null }
  >;
};


precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
clientsClaim();

self.addEventListener("install", () => {
  void self.skipWaiting();
});


registerRoute(
  ({ url, request }) => (
    request.method === API_RUNTIME_CACHING.method &&
    API_RUNTIME_CACHING.urlPattern.test(url.href)
  ),
  new NetworkOnly(),
  "GET",
);

self.addEventListener("push", (event) => {
  event.waitUntil(handlePush(event));
});

async function handlePush(event: PushEvent): Promise<void> {
  let raw: unknown;
  try {
    raw = event.data?.json();
  } catch {
    return;
  }

  const payload = parsePushPayload(raw);
  if (!payload) {
    return;
  }

  await self.registration.showNotification(
    payload.title,
    buildNotificationOptions(payload),
  );
}

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const data = event.notification.data;
  const targetUrl = (
    typeof data === "object" &&
    data !== null &&
    typeof data.url === "string"
  )
    ? data.url
    : null;

  if (!targetUrl) {
    return;
  }

  event.waitUntil(
    handleNotificationClick(
      self.clients as unknown as WindowClientsLike,
      targetUrl,
      self.location.origin,
    ),
  );
});
