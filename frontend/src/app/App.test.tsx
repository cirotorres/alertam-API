import { render, screen } from "@testing-library/react";

import { App } from "./App";

test("renders_alertam_shell_title", () => {
  render(<App />);

  expect(
    screen.getByRole("heading", { name: "Alerta de Movimentações Marítimas" }),
  ).toBeInTheDocument();
});
