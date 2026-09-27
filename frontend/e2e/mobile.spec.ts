import { expect, test, type Page } from "@playwright/test";

import { BERTH_POSITIONS } from "../src/features/map/berthMap";
import {
  onlineResponse,
  PAIRING_KEY,
  staleResponse,
  storedPairing,
  TOKEN,
} from "./fixtures";

async function mockSnapshot(
  page: Page,
  options: {
    status?: number;
    body?: unknown;
    count?: { value: number };
  } = {},
) {
  await page.route("**/api/v1/devices/**/snapshot", async (route) => {
    if (options.count) options.count.value += 1;
    const status = options.status ?? 200;
    await route.fulfill({
      status,
      contentType: "application/json",
      body:
        status === 200
          ? JSON.stringify(options.body ?? onlineResponse)
          : JSON.stringify({ detail: "mock" }),
    });
  });
}

async function mockMobileSession(
  page: Page,
  recoverDeviceId: string | null = null,
) {
  await page.route("**/api/v1/mobile/session", async (route) => {
    const method = route.request().method();

    if (method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ device_id: "pecem-01" }),
      });
      return;
    }

    if (method === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }

    if (recoverDeviceId) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ device_id: recoverDeviceId }),
      });
      return;
    }

    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: { code: "invalid_view_credentials" } }),
    });
  });
}

async function seedPairing(page: Page) {
  await mockMobileSession(page);
  await page.addInitScript(
    ({ key, value }) => localStorage.setItem(key, JSON.stringify(value)),
    { key: PAIRING_KEY, value: storedPairing() },
  );
}

async function expectNoHorizontalOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(sizes.scroll).toBeLessThanOrEqual(sizes.width);
}
test("pairing removes token from url and renders operational data", async ({ page }) => {
  await mockSnapshot(page);
  await mockMobileSession(page);

  await page.goto(`/#/pair/pecem-01?token=${TOKEN}`);

  await expect(page.getByText("Sistema ativo")).toBeVisible();
  await expect(page.getByRole("button", { name: /NAVIO A, Berço 2/i })).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  expect(page.url()).not.toContain(TOKEN);
  expect(await page.evaluate(() => document.body.textContent)).not.toContain(TOKEN);
  expect(
    await page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? "null").deviceId, PAIRING_KEY),
  ).toBe("pecem-01");
  await expectNoHorizontalOverflow(page);
});

test("operational navigation, vessel sheet and drawer work together", async ({ page }) => {
  await seedPairing(page);
  await mockSnapshot(page);
  await page.goto("/");

  await page.getByRole("button", { name: "Prev. atracação" }).click();
  await expect(page.getByRole("heading", { name: "Previsão de atracação" })).toBeVisible();

  await page.getByRole("button", { name: /NAVIO A, Berço 2/i }).click();
  await expect(page.getByRole("dialog", { name: /Ficha do navio NAVIO A/i })).toBeVisible();

  await page.getByRole("button", { name: "Abrir menu" }).click();
  await expect(page.getByRole("dialog", { name: "Menu principal" })).toBeVisible();
  await expect(page.getByRole("dialog", { name: /Ficha do navio/i })).toHaveCount(0);

  await page.getByRole("link", { name: "Alertas" }).click();
  await expect(page.getByRole("heading", { name: "Alertas" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Prev. desatracação" })).toBeVisible();

  await page.getByRole("button", { name: "Abrir menu" }).click();
  await page.getByRole("link", { name: "Histórico" }).click();
  await expect(page.getByRole("heading", { name: "Histórico" })).toBeVisible();

  await page.getByRole("button", { name: "Abrir menu" }).click();
  await page.getByRole("link", { name: "Config." }).click();
  await expect(page.getByRole("heading", { name: "Config." })).toBeVisible();

  await page.getByRole("button", { name: "Abrir menu" }).click();
  await page.getByRole("link", { name: "Sobre" }).click();
  await expect(page.getByRole("heading", { name: "Sobre o AlertaM" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
test("waiting, stale, revoked and temporary offline states are handled", async ({ page }) => {
  await seedPairing(page);

  await mockSnapshot(page, { status: 404 });
  await page.goto("/");
  await expect(page.getByText("Aguardando primeira leitura")).toBeVisible();

  await page.unroute("**/api/v1/devices/**/snapshot");
  await mockSnapshot(page, { body: staleResponse });
  await page.reload();
  await expect(page.getByText("Dados desatualizados")).toBeVisible();

  await page.unroute("**/api/v1/devices/**/snapshot");
  let calls = 0;
  await page.route("**/api/v1/devices/**/snapshot", async (route) => {
    calls += 1;
    if (calls === 1) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(onlineResponse),
      });
      return;
    }
    await route.abort("failed");
  });
  await page.reload();
  await expect(page.getByText("Sistema ativo")).toBeVisible();
  await page.getByRole("button", { name: "Abrir menu" }).click();
  await page.getByRole("link", { name: "Mapa" }).click();
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(page.getByText("Sem conexão com o servidor")).toBeVisible();
  await expect(page.getByRole("button", { name: /NAVIO A, Berço 2/i })).toBeVisible();

  await page.unroute("**/api/v1/devices/**/snapshot");
  await mockSnapshot(page, { status: 401 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Alerta de Movimentações Marítimas" }),
  ).toBeVisible();
  await expect(page.getByText(/Conectar Celular/i)).toBeVisible();
});
test("visibility changes pause hidden polling and fetch immediately on return", async ({ page }) => {
  await seedPairing(page);
  const count = { value: 0 };
  await mockSnapshot(page, { count });
  await page.goto("/");
  await expect(page.getByText("Sistema ativo")).toBeVisible();
  expect(count.value).toBe(1);

  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(1_000);
  expect(count.value).toBe(1);

  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => count.value).toBe(2);
});

test("forget device clears local pairing and returns to gate", async ({ page }) => {
  await seedPairing(page);
  await mockSnapshot(page);
  await page.goto("/config");

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Esquecer este aparelho" }).click();

  await expect(
    page.getByRole("heading", { name: "Alerta de Movimentações Marítimas" }),
  ).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), PAIRING_KEY)).toBeNull();
});
test("installed shell reloads offline without cached authenticated snapshot", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-390", "Service worker offline smoke runs once.");

  const context = await browser.newContext({
    baseURL: "http://127.0.0.1:4173",
    viewport: { width: 390, height: 844 },
    serviceWorkers: "allow",
  });
  const page = await context.newPage();

  await seedPairing(page);
  await mockSnapshot(page);
  await page.goto("/");
  await expect(page.getByText("Sistema ativo")).toBeVisible();

  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);

  await context.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded" });

  await expect(page.getByText("Sem conexão com o servidor")).toBeVisible();
  await expect(page.getByRole("button", { name: /NAVIO A, Berço 2/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Abrir menu" })).toBeVisible();

  await context.close();
});


test("demo mode shows mocked maneuvers without calling the real api", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-390", "Demo validation runs once on mobile.");

  let apiCalls = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) {
      apiCalls += 1;
    }
  });

  await page.goto("/demo");

  await expect(page.getByText("Modo demonstração")).toBeVisible();
  await expect(page.getByText(/Dados fictícios para validação visual/i)).toBeVisible();

  const arriving = page.getByRole("button", {
    name: /ATLANTIC DAWN, Berço 2/i,
  });
  const departing = page.getByRole("button", {
    name: /OCEAN STAR, Berço 7/i,
  });

  await expect(arriving).toBeVisible();
  await expect(departing).toBeVisible();
  await expect(arriving.locator(".port-map__ship-base")).toHaveAttribute(
    "src",
    "/assets/navio.png",
  );
  await expect(arriving.locator(".port-map__ship-overlay")).toHaveAttribute(
    "src",
    "/assets/navio_green.png",
  );
  await expect(departing.locator(".port-map__ship-base")).toHaveAttribute(
    "src",
    "/assets/navio.png",
  );
  await expect(departing.locator(".port-map__ship-overlay")).toHaveAttribute(
    "src",
    "/assets/navio_red.png",
  );

  const spriteBackground = await arriving
    .locator(".port-map__sprite")
    .evaluate((element) => getComputedStyle(element).backgroundColor);
  const arrivingAnimation = await arriving
    .locator(".port-map__ship-overlay")
    .evaluate((element) => getComputedStyle(element).animationName);
  const departingAnimation = await departing
    .locator(".port-map__ship-overlay")
    .evaluate((element) => getComputedStyle(element).animationName);
  const arrivingRingAnimation = await arriving
    .locator(".port-map__sprite")
    .evaluate((element) => getComputedStyle(element, "::before").animationName);
  const departingRingAnimation = await departing
    .locator(".port-map__sprite")
    .evaluate((element) => getComputedStyle(element, "::before").animationName);

  expect(spriteBackground).toBe("rgba(0, 0, 0, 0)");
  expect(arrivingAnimation).toContain("alertam-ship-color-cycle");
  expect(departingAnimation).toContain("alertam-ship-color-cycle");
  expect(arrivingRingAnimation).toContain("alertam-status-ring");
  expect(departingRingAnimation).toContain("alertam-status-ring");

  await expect(page.locator(".port-map__vessel")).toHaveCount(10);
  await expect(page.locator(".port-map__canvas")).not.toHaveClass(
    /port-map__canvas--dense/,
  );
  const demoSpriteSize = await page.locator(".port-map__sprite").first().evaluate(
    (element) => {
      const style = getComputedStyle(element);
      return {
        width: Number.parseFloat(style.width),
        height: Number.parseFloat(style.height),
      };
    },
  );
  expect(demoSpriteSize.width).toBeGreaterThanOrEqual(38);
  expect(demoSpriteSize.width).toBeLessThanOrEqual(50);
  expect(demoSpriteSize.height).toBe(demoSpriteSize.width);

  for (const [berth, position] of Object.entries(BERTH_POSITIONS)) {
    const marker = page.getByRole("button", {
      name: new RegExp(`Berço ${berth}$`, "i"),
    });
    await expect(marker).toHaveCSS("left", /.+/);
    expect(await marker.evaluate((element) => element.style.left)).toBe(
      `${position.xPct}%`,
    );
    expect(await marker.evaluate((element) => element.style.top)).toBe(
      `${position.yPct}%`,
    );
  }

  const fixedMapBefore = await page.locator(".map-page__fixed").boundingBox();
  const statusBefore = await page.locator(".status-stack").boundingBox();
  const scrollArea = page.locator(".operational-list");
  const windowScrollBefore = await page.evaluate(() => window.scrollY);
  const scrollStyle = await scrollArea.evaluate(
    (element) => getComputedStyle(element).overflowY,
  );

  await scrollArea.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });

  const fixedMapAfter = await page.locator(".map-page__fixed").boundingBox();
  const statusAfter = await page.locator(".status-stack").boundingBox();
  const windowScrollAfter = await page.evaluate(() => window.scrollY);

  expect(scrollStyle).toBe("auto");
  expect(windowScrollBefore).toBe(0);
  expect(windowScrollAfter).toBe(0);
  expect(fixedMapBefore?.y).toBe(fixedMapAfter?.y);
  expect(statusBefore?.y).toBe(statusAfter?.y);

  const layout = await page.evaluate(() => {
    const header = document.querySelector(".mobile-header")?.getBoundingClientRect();
    const map = document.querySelector(".port-map__canvas")?.getBoundingClientRect();
    const footer = document.querySelector(".bottom-nav")?.getBoundingClientRect();
    const cards = Array.from(
      document.querySelectorAll(".reading-card, .system-card"),
    ).map((element) => element.getBoundingClientRect().height);
    return {
      header: header?.height ?? 0,
      map: map?.height ?? 0,
      footer: footer?.height ?? 0,
      cards,
    };
  });

  expect(layout.header).toBeLessThanOrEqual(80);
  expect(layout.map).toBeGreaterThanOrEqual(330);
  expect(layout.map).toBeLessThanOrEqual(340);
  expect(layout.footer).toBeLessThanOrEqual(66);
  expect(layout.cards.every((height) => height <= 54)).toBe(true);

  await page.getByRole("button", { name: "Prev. desatracação" }).click();
  await expect(
    page.getByRole("heading", { name: "Previsão de desatracação" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Abrir menu" }).click();
  const alerts = page.getByRole("link", { name: "Alertas" });
  await expect(alerts).toHaveAttribute("href", "/demo/alertas");
  await alerts.click();
  await expect(page.getByRole("heading", { name: "Alertas" })).toBeVisible();

  expect(apiCalls).toBe(0);
});


test("installed_pwa_recovers_cookie_session_without_local_storage", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-390", "Cookie recovery smoke runs once.");

  await mockMobileSession(page, "pecem-01");

  let snapshotAuthorization: string | undefined;
  await page.route("**/api/v1/devices/pecem-01/snapshot", async (route) => {
    snapshotAuthorization = route.request().headers()["authorization"];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(onlineResponse),
    });
  });

  await page.goto("/");

  await expect(page.getByText("Sistema ativo")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /NAVIO A, Berço 2/i }),
  ).toBeVisible();

  expect(
    await page.evaluate((key) => localStorage.getItem(key), PAIRING_KEY),
  ).toBeNull();
  expect(snapshotAuthorization).toBeUndefined();
});
