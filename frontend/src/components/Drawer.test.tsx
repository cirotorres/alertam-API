import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";

import { Drawer } from "./Drawer";

function renderDrawer(onClose = vi.fn()) {
  const view = render(
    <MemoryRouter>
      <Drawer open onClose={onClose} />
    </MemoryRouter>,
  );
  return { ...view, onClose };
}

test("short_left_drag_keeps_drawer_open", () => {
  const { onClose } = renderDrawer();
  const drawer = screen.getByRole("dialog", { name: "Menu principal" });

  fireEvent.pointerDown(drawer, {
    pointerId: 1,
    isPrimary: true,
    button: 0,
    clientX: 260,
  });
  fireEvent.pointerMove(drawer, { pointerId: 1, clientX: 225 });
  fireEvent.pointerUp(drawer, { pointerId: 1, clientX: 225 });

  expect(onClose).not.toHaveBeenCalled();
});

test("long_left_drag_dismisses_drawer", async () => {
  const { onClose } = renderDrawer();
  const drawer = screen.getByRole("dialog", { name: "Menu principal" });

  fireEvent.pointerDown(drawer, {
    pointerId: 2,
    isPrimary: true,
    button: 0,
    clientX: 260,
  });
  fireEvent.pointerMove(drawer, { pointerId: 2, clientX: 110 });
  fireEvent.pointerUp(drawer, { pointerId: 2, clientX: 110 });

  await vi.waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
});


test("drawer_locks_background_scroll_while_rendered", () => {
  const { unmount } = renderDrawer();

  expect(document.documentElement).toHaveClass("has-open-drawer");

  unmount();

  expect(document.documentElement).not.toHaveClass("has-open-drawer");
});


test("drawer_keeps_weather_out_of_general_navigation", () => {
  renderDrawer();
  expect(screen.queryByRole("link", { name: "Tempo" })).not.toBeInTheDocument();
});


test("drawer_links_to_tracked_vessels_page", () => {
  renderDrawer();
  expect(screen.getByRole("link", { name: "Acompanhados" })).toHaveAttribute(
    "href",
    "/acompanhados",
  );
});
