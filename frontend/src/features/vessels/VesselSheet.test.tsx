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
