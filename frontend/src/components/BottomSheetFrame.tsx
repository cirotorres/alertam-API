import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { useDismissDrag } from "../hooks/useDismissDrag";


type BottomSheetFrameProps = {
  open: boolean;
  onClose: () => void;
  ariaLabel: string;
  closeLabel: string;
  children: ReactNode;
};

export function BottomSheetFrame({
  open,
  onClose,
  ariaLabel,
  closeLabel,
  children,
}: BottomSheetFrameProps) {
  const [atScrollTop, setAtScrollTop] = useState(true);
  const [upwardPull, setUpwardPull] = useState(0);
  const touchStartYRef = useRef<number | null>(null);
  const touchScrollModeRef = useRef(false);
  const dragFromHandleRef = useRef(false);

  const canStartDrag = useCallback((
    target: EventTarget | null,
    currentTarget: HTMLElement,
  ) => {
    if (currentTarget.scrollTop > 0) return false;
    return !(
      target instanceof Element &&
      target.closest("a, button, input, select, textarea")
    );
  }, []);

  const drag = useDismissDrag({
    axis: "y",
    direction: "positive",
    onDismiss: onClose,
    canStart: canStartDrag,
  });

  useEffect(() => {
    if (!open) return;
    drag.reset();
    setUpwardPull(0);
    touchStartYRef.current = null;
    touchScrollModeRef.current = false;
    dragFromHandleRef.current = false;
  }, [open]);

  const dragActive = drag.interacted && (open || drag.dismissing);
  const sheetStyle = dragActive
    ? {
        transform: `translate(-50%, ${drag.offset - upwardPull}px)`,
        transition: drag.dragging
          ? "none"
          : "transform 180ms cubic-bezier(0.22, 1, 0.36, 1)",
      }
    : undefined;
  const backdropStyle = dragActive
    ? {
        opacity: Math.max(0, 1 - drag.progress * 0.92),
        transition: drag.dragging ? "none" : "opacity 180ms ease-out",
      }
    : undefined;
  const dragClasses = [
    drag.interacted ? "is-drag-interacted" : "",
    drag.dragging ? "is-dragging" : "",
    drag.dismissing ? "is-drag-dismissing" : "",
  ].filter(Boolean).join(" ");

  return (
    <>
      <button
        className={`bottom-sheet-frame__backdrop vessel-sheet-backdrop ${open ? "is-open" : "is-closing"} ${dragClasses}`}
        style={backdropStyle}
        type="button"
        aria-label={`Fechar ${ariaLabel.toLocaleLowerCase("pt-BR")} pela área externa`}
        aria-hidden={!open}
        disabled={!open}
        onClick={onClose}
      />
      <aside
        className={`bottom-sheet-frame vessel-sheet ${open ? "is-open" : "is-closing"} ${atScrollTop ? "is-at-scroll-top" : ""} ${dragClasses}`}
        style={sheetStyle}
        role="dialog"
        aria-modal="true"
        aria-hidden={!open}
        aria-label={ariaLabel}
        onPointerDown={(event) => {
          if (
            event.pointerType === "touch" &&
            canStartDrag(event.target, event.currentTarget)
          ) {
            touchStartYRef.current = event.clientY;
            touchScrollModeRef.current = false;
            dragFromHandleRef.current = Boolean(
              event.target instanceof Element &&
              event.target.closest(".bottom-sheet-frame__drag-zone"),
            );
          }
          drag.pointerHandlers.onPointerDown(event);
        }}
        onPointerMove={(event) => {
          const touchStartY = touchStartYRef.current;
          if (event.pointerType === "touch" && touchStartY !== null) {
            const signedDelta = event.clientY - touchStartY;
            if (dragFromHandleRef.current && signedDelta < 0) {
              setUpwardPull(Math.min(36, Math.abs(signedDelta) * 0.24));
              return;
            }
            if (
              touchScrollModeRef.current ||
              (!dragFromHandleRef.current && signedDelta < -6)
            ) {
              touchScrollModeRef.current = true;
              setUpwardPull(0);
              event.currentTarget.scrollTop = Math.max(0, -signedDelta);
              setAtScrollTop(event.currentTarget.scrollTop <= 0);
              return;
            }
          }
          setUpwardPull(0);
          drag.pointerHandlers.onPointerMove(event);
        }}
        onPointerUp={(event) => {
          if (touchScrollModeRef.current || upwardPull > 0) {
            drag.pointerHandlers.onPointerCancel(event);
          } else {
            drag.pointerHandlers.onPointerUp(event);
          }
          setUpwardPull(0);
          touchStartYRef.current = null;
          touchScrollModeRef.current = false;
          dragFromHandleRef.current = false;
        }}
        onPointerCancel={(event) => {
          drag.pointerHandlers.onPointerCancel(event);
          setUpwardPull(0);
          touchStartYRef.current = null;
          touchScrollModeRef.current = false;
          dragFromHandleRef.current = false;
        }}
        onScroll={(event) => setAtScrollTop(event.currentTarget.scrollTop <= 0)}
      >
        <div
          className="bottom-sheet-frame__drag-zone vessel-sheet__drag-zone"
          aria-hidden="true"
        >
          <div className="bottom-sheet-frame__handle vessel-sheet__handle" />
        </div>
        <button
          type="button"
          className="bottom-sheet-frame__close"
          autoFocus={open}
          onClick={onClose}
          aria-label={closeLabel}
        >
          ×
        </button>
        <div className="bottom-sheet-frame__content">{children}</div>
      </aside>
    </>
  );
}
