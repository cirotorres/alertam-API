import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../../api/contract";
import { VesselSheet } from "./VesselSheet";

const vessel = parseSnapshotReadResponse({
  snapshot: fixture,
  meta: {
    received_at: "2026-09-25T13:40:15-03:00",
    age_seconds: 3,
    collector_online: true,
    stale_after_seconds: 120,
  },
}).snapshot.vessels[0];

test("renders_real_vessel_fields_without_fake_photo", () => {
  const onClose = vi.fn();

  render(<VesselSheet vessel={vessel} open onClose={onClose} />);

  expect(screen.getByRole("dialog", { name: /NAVIO A/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Fechar ficha do navio" })).toHaveFocus();
  for (const value of ["1234567", "ATRACANDO", "25/09 12:00", "Berço 2", "SANTOS", "R1, R2", "PPAA"]) {
    expect(screen.getByText(value, { exact: false })).toBeInTheDocument();
  }
  expect(screen.getByText("AG", { exact: true })).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Fechar ficha do navio" }));
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("does_not_render_when_closed", () => {
  render(<VesselSheet vessel={vessel} open={false} onClose={() => undefined} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("short_downward_drag_keeps_vessel_sheet_open", () => {
  const onClose = vi.fn();
  const { container } = render(
    <VesselSheet vessel={vessel} open onClose={onClose} />,
  );
  const sheet = screen.getByRole("dialog", { name: /NAVIO A/i });
  const grab = container.querySelector(".vessel-sheet__drag-zone");
  expect(grab).not.toBeNull();

  fireEvent.pointerDown(grab!, {
    pointerId: 1,
    isPrimary: true,
    button: 0,
    clientY: 100,
  });
  fireEvent.pointerMove(sheet, { pointerId: 1, clientY: 135 });
  fireEvent.pointerUp(sheet, { pointerId: 1, clientY: 135 });

  expect(onClose).not.toHaveBeenCalled();
});

test("long_downward_drag_dismisses_vessel_sheet", async () => {
  const onClose = vi.fn();
  const { container } = render(
    <VesselSheet vessel={vessel} open onClose={onClose} />,
  );
  const sheet = screen.getByRole("dialog", { name: /NAVIO A/i });
  const grab = container.querySelector(".vessel-sheet__drag-zone");
  expect(grab).not.toBeNull();

  fireEvent.pointerDown(grab!, {
    pointerId: 2,
    isPrimary: true,
    button: 0,
    clientY: 100,
  });
  fireEvent.pointerMove(sheet, { pointerId: 2, clientY: 240 });
  fireEvent.pointerUp(sheet, { pointerId: 2, clientY: 240 });

  await vi.waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
});
