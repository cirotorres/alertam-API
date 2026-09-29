import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { BottomSheetFrame } from "./BottomSheetFrame";


afterEach(() => {
  document.documentElement.classList.remove("has-open-bottom-sheet");
});

function renderFrame(onClose = vi.fn(), open = true) {
  const view = render(
    <BottomSheetFrame
      open={open}
      onClose={onClose}
      ariaLabel="Detalhes de teste"
      closeLabel="Fechar detalhes"
    >
      <p>Conteúdo</p>
      <button type="button">Ação interna</button>
    </BottomSheetFrame>,
  );
  return { ...view, onClose };
}

test("bottom_sheet_locks_document_only_while_open_and_cleans_up_on_unmount", () => {
  const onClose = vi.fn();
  const { rerender, unmount } = render(
    <BottomSheetFrame
      open
      onClose={onClose}
      ariaLabel="Detalhes de teste"
      closeLabel="Fechar detalhes"
    >
      <p>Conteúdo</p>
    </BottomSheetFrame>,
  );

  expect(document.documentElement).toHaveClass("has-open-bottom-sheet");

  rerender(
    <BottomSheetFrame
      open={false}
      onClose={onClose}
      ariaLabel="Detalhes de teste"
      closeLabel="Fechar detalhes"
    >
      <p>Conteúdo</p>
    </BottomSheetFrame>,
  );
  expect(document.documentElement).not.toHaveClass("has-open-bottom-sheet");

  rerender(
    <BottomSheetFrame
      open
      onClose={onClose}
      ariaLabel="Detalhes de teste"
      closeLabel="Fechar detalhes"
    >
      <p>Conteúdo</p>
    </BottomSheetFrame>,
  );
  expect(document.documentElement).toHaveClass("has-open-bottom-sheet");

  unmount();
  expect(document.documentElement).not.toHaveClass("has-open-bottom-sheet");
});

test("bottom_sheet_document_lock_is_reference_counted", () => {
  const { rerender, unmount } = render(
    <>
      <BottomSheetFrame
        open
        onClose={() => undefined}
        ariaLabel="Primeira sheet"
        closeLabel="Fechar primeira"
      >
        <p>Primeira</p>
      </BottomSheetFrame>
      <BottomSheetFrame
        open
        onClose={() => undefined}
        ariaLabel="Segunda sheet"
        closeLabel="Fechar segunda"
      >
        <p>Segunda</p>
      </BottomSheetFrame>
    </>,
  );

  expect(document.documentElement).toHaveClass("has-open-bottom-sheet");

  rerender(
    <>
      <BottomSheetFrame
        open={false}
        onClose={() => undefined}
        ariaLabel="Primeira sheet"
        closeLabel="Fechar primeira"
      >
        <p>Primeira</p>
      </BottomSheetFrame>
      <BottomSheetFrame
        open
        onClose={() => undefined}
        ariaLabel="Segunda sheet"
        closeLabel="Fechar segunda"
      >
        <p>Segunda</p>
      </BottomSheetFrame>
    </>,
  );

  expect(document.documentElement).toHaveClass("has-open-bottom-sheet");

  unmount();
  expect(document.documentElement).not.toHaveClass("has-open-bottom-sheet");
});

test("bottom_sheet_backdrop_and_close_button_close_the_frame", () => {
  const { onClose } = renderFrame();

  fireEvent.click(screen.getByRole("button", { name: "Fechar detalhes" }));
  expect(onClose).toHaveBeenCalledTimes(1);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Fechar detalhes de teste pela área externa",
    }),
  );
  expect(onClose).toHaveBeenCalledTimes(2);
});

test("bottom_sheet_is_hidden_from_accessibility_tree_when_closed", () => {
  renderFrame(vi.fn(), false);

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("bottom_sheet_long_downward_drag_dismisses_from_body_at_top", async () => {
  const { onClose } = renderFrame();
  const sheet = screen.getByRole("dialog", { name: "Detalhes de teste" });
  const body = screen.getByText("Conteúdo");

  fireEvent.pointerDown(body, {
    pointerId: 1,
    isPrimary: true,
    button: 0,
    clientY: 100,
  });
  fireEvent.pointerMove(sheet, { pointerId: 1, clientY: 250 });
  fireEvent.pointerUp(sheet, { pointerId: 1, clientY: 250 });

  await vi.waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
});

test("bottom_sheet_short_downward_drag_does_not_dismiss", () => {
  const { container, onClose } = renderFrame();
  const sheet = screen.getByRole("dialog", { name: "Detalhes de teste" });
  const handle = container.querySelector(".bottom-sheet-frame__drag-zone");

  fireEvent.pointerDown(handle!, {
    pointerId: 2,
    isPrimary: true,
    button: 0,
    clientY: 100,
  });
  fireEvent.pointerMove(sheet, { pointerId: 2, clientY: 135 });
  fireEvent.pointerUp(sheet, { pointerId: 2, clientY: 135 });

  expect(onClose).not.toHaveBeenCalled();
});

test("bottom_sheet_interactive_control_does_not_start_drag", () => {
  const { onClose } = renderFrame();
  const sheet = screen.getByRole("dialog", { name: "Detalhes de teste" });
  const action = screen.getByRole("button", { name: "Ação interna" });

  fireEvent.pointerDown(action, {
    pointerId: 3,
    isPrimary: true,
    button: 0,
    clientY: 100,
  });
  fireEvent.pointerMove(sheet, { pointerId: 3, clientY: 300 });
  fireEvent.pointerUp(sheet, { pointerId: 3, clientY: 300 });

  expect(onClose).not.toHaveBeenCalled();
});

test("bottom_sheet_does_not_drag_while_scrolled", () => {
  const { onClose } = renderFrame();
  const sheet = screen.getByRole("dialog", { name: "Detalhes de teste" });
  const body = screen.getByText("Conteúdo");
  Object.defineProperty(sheet, "scrollTop", { value: 80, writable: true });
  fireEvent.scroll(sheet);

  fireEvent.pointerDown(body, {
    pointerId: 4,
    isPrimary: true,
    button: 0,
    clientY: 100,
  });
  fireEvent.pointerMove(sheet, { pointerId: 4, clientY: 300 });
  fireEvent.pointerUp(sheet, { pointerId: 4, clientY: 300 });

  expect(onClose).not.toHaveBeenCalled();
});

test("bottom_sheet_upward_handle_pull_is_resisted_and_snaps_back", async () => {
  const { container, onClose } = renderFrame();
  const sheet = screen.getByRole("dialog", { name: "Detalhes de teste" });
  const handle = container.querySelector(".bottom-sheet-frame__drag-zone");

  fireEvent.pointerDown(handle!, {
    pointerId: 5,
    isPrimary: true,
    button: 0,
    pointerType: "touch",
    clientY: 180,
  });
  fireEvent.pointerMove(sheet, {
    pointerId: 5,
    pointerType: "touch",
    clientY: 100,
  });

  expect(sheet.style.transform).toMatch(/translate\(-50%, -\d/);

  fireEvent.pointerUp(sheet, {
    pointerId: 5,
    pointerType: "touch",
    clientY: 100,
  });

  await vi.waitFor(() => expect(sheet.style.transform).toContain("0px"));
  expect(onClose).not.toHaveBeenCalled();
});
