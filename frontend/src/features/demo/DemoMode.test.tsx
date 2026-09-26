import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { App } from "../../app/App";

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/demo");
  vi.restoreAllMocks();
});

test("demo_bypasses_pairing_and_shows_arrival_and_departure_in_progress", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);

  expect(await screen.findByText("Modo demonstração")).toBeInTheDocument();
  const arriving = screen.getByRole("button", {
    name: /ATLANTIC DAWN, Berço 2/i,
  });
  const departing = screen.getByRole("button", {
    name: /OCEAN STAR, Berço 7/i,
  });
  expect(arriving).toHaveClass("port-map__vessel--arriving");
  expect(departing).toHaveClass("port-map__vessel--departing");
  expect(fetchMock).not.toHaveBeenCalled();
});

test("demo_navigation_stays_under_demo_prefix", async () => {
  vi.stubGlobal("fetch", vi.fn());
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: "Abrir menu" }));
  const alerts = screen.getByRole("link", { name: "Alertas" });
  expect(alerts).toHaveAttribute("href", "/demo/alertas");

  fireEvent.click(alerts);
  expect(
    await screen.findByRole("heading", { name: "Alertas" }),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Prev. desatracação" }));
  expect(
    await screen.findByRole("heading", { name: "Previsão de desatracação" }),
  ).toBeInTheDocument();
  expect(window.location.pathname).toBe("/demo");
});
