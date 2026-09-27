import { fireEvent, render, screen } from "@testing-library/react";
import { BottomNav } from "./BottomNav";

test("shows_four_operational_tabs_plus_weather_and_changes_selection", () => {
  const changes: string[] = [];
  const { rerender } = render(
    <BottomNav active="maneuvers" onChange={(value) => changes.push(value)} />,
  );

  for (const label of ["Manobras confirmadas", "Prev. atracação", "Prev. desatracação", "Fundeados", "Tempo"]) {
    expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
  }

  fireEvent.click(screen.getByRole("button", { name: "Prev. atracação" }));
  fireEvent.click(screen.getByRole("button", { name: "Tempo" }));
  expect(changes).toEqual(["arrivals", "weather"]);

  rerender(<BottomNav active="weather" onChange={() => undefined} />);
  expect(screen.getByRole("button", { name: "Tempo" })).toHaveAttribute("aria-current", "page");
});
