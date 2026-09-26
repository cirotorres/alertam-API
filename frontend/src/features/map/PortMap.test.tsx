import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";
import fixture from "../../test/fixtures/mobile_snapshot_v1.json";
import { parseSnapshotReadResponse } from "../../api/contract";
import { PortMap } from "./PortMap";

test("positions_vessel_with_percentages_and_emits_selection", () => {
  const snapshot = parseSnapshotReadResponse({
    snapshot: fixture,
    meta: { received_at: "2026-09-25T13:40:15-03:00", age_seconds: 3, collector_online: true, stale_after_seconds: 120 },
  }).snapshot;
  const onSelect = vi.fn();

  render(<PortMap snapshot={snapshot} onSelectVessel={onSelect} />);

  const pin = screen.getByRole("button", { name: /NAVIO A.*Berço 2/i });
  expect(pin).toHaveClass("port-map__vessel--arriving");
  expect(pin).toHaveStyle({ left: "41%", top: "64%" });
  expect(pin.style.left).not.toContain("px");
  expect(screen.getByRole("img", { name: /Mapa esquemático/i })).toHaveAttribute("src", "/assets/piers.png");
  expect(screen.getByText("Porto do Pecém (CIPP) - CE")).toBeInTheDocument();
  expect(screen.queryByText(/- CE - CE/)).not.toBeInTheDocument();

  fireEvent.click(pin);
  expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ name: "NAVIO A" }));
});
