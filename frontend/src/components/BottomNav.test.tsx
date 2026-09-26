import { fireEvent, render, screen } from "@testing-library/react";
import { BottomNav } from "./BottomNav";

test("shows_four_operational_tabs_and_changes_selection", () => {
  const changes: string[] = [];
  const { rerender } = render(
    <BottomNav active="maneuvers" onChange={(value) => changes.push(value)} />,
  );

  for (const label of ["Manobras confirmadas", "Prev. atracação", "Prev. desatracação", "Fundeados"]) {
    expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
  }

  fireEvent.click(screen.getByRole("button", { name: "Prev. atracação" }));
  expect(changes).toEqual(["arrivals"]);

  rerender(<BottomNav active="arrivals" onChange={() => undefined} />);
  expect(screen.getByRole("button", { name: "Prev. atracação" })).toHaveAttribute("aria-current", "page");
});
