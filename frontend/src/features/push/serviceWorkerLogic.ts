export type PushNotificationPayload = {
  event_id: string;
  title: string;
  body: string;
  url: string;
};

export type PushNotificationOptions = {
  body: string;
  tag: string;
  renotify: false;
  data: {
    url: string;
    event_id: string;
  };
};

export type WindowClientLike = {
  url: string;
  navigate: (url: string) => Promise<unknown>;
  focus: () => Promise<unknown>;
};

export type WindowClientsLike = {
  matchAll: (
    options: { type: "window"; includeUncontrolled: true },
  ) => Promise<WindowClientLike[]>;
  openWindow: (url: string) => Promise<unknown>;
};


function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parsePushPayload(
  value: unknown,
): PushNotificationPayload | null {
  if (!isRecord(value)) {
    return null;
  }

  const eventId = value.event_id;
  const title = value.title;
  const body = value.body;
  const url = value.url;
  if (
    typeof eventId !== "string" ||
    eventId.length === 0 ||
    typeof title !== "string" ||
    title.length === 0 ||
    typeof body !== "string" ||
    typeof url !== "string" ||
    !url.startsWith("/") ||
    url.startsWith("//")
  ) {
    return null;
  }

  return {
    event_id: eventId,
    title,
    body,
    url,
  };
}

export function buildNotificationOptions(
  payload: PushNotificationPayload,
): PushNotificationOptions {
  return {
    body: payload.body,
    tag: payload.event_id,
    renotify: false,
    data: {
      url: payload.url,
      event_id: payload.event_id,
    },
  };
}


function isSameOrigin(url: string, origin: string): boolean {
  try {
    return new URL(url).origin === origin;
  } catch {
    return false;
  }
}

export async function handleNotificationClick(
  clientsApi: WindowClientsLike,
  targetUrl: string,
  origin: string,
): Promise<void> {
  const target = new URL(targetUrl, origin);
  if (target.origin !== origin) {
    return;
  }

  const windows = await clientsApi.matchAll({
    type: "window",
    includeUncontrolled: true,
  });
  const existing = windows.find((client) =>
    isSameOrigin(client.url, origin)
  );

  if (existing) {
    await existing.navigate(target.href);
    await existing.focus();
    return;
  }

  await clientsApi.openWindow(target.href);
}
