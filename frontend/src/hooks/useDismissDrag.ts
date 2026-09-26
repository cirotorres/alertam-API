import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

type DragAxis = "x" | "y";
type DragDirection = "negative" | "positive";

type UseDismissDragOptions = {
  axis: DragAxis;
  direction: DragDirection;
  onDismiss: () => void;
  canStart?: (target: EventTarget | null) => boolean;
};

type DragStart = {
  pointerId: number;
  coordinate: number;
  startedAt: number;
  extent: number;
};

const DISMISS_DURATION_MS = 180;
const MIN_DISTANCE_PX = 64;
const MAX_DISTANCE_PX = 96;
const MIN_FLING_DURATION_MS = 40;
const FLING_VELOCITY_PX_MS = 0.65;

function coordinateFor(
  event: ReactPointerEvent<HTMLElement>,
  axis: DragAxis,
) {
  return axis === "x" ? event.clientX : event.clientY;
}

function directedDistance(
  start: number,
  current: number,
  direction: DragDirection,
) {
  const delta = direction === "positive" ? current - start : start - current;
  return Math.max(0, delta);
}

export function useDismissDrag({
  axis,
  direction,
  onDismiss,
  canStart,
}: UseDismissDragOptions) {
  const [offset, setOffset] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [interacted, setInteracted] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const startRef = useRef<DragStart | null>(null);
  const dismissTimerRef = useRef<number | null>(null);

  const clearDismissTimer = useCallback(() => {
    if (dismissTimerRef.current !== null) {
      window.clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    clearDismissTimer();
    startRef.current = null;
    setOffset(0);
    setDragging(false);
    setInteracted(false);
    setDismissing(false);
  }, [clearDismissTimer]);

  useEffect(() => clearDismissTimer, [clearDismissTimer]);

  const onPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      if (
        event.isPrimary === false ||
        event.button !== 0 ||
        canStart?.(event.target) === false
      ) {
        return;
      }

      const rect = event.currentTarget.getBoundingClientRect();
      const measuredExtent = axis === "x" ? rect.width : rect.height;
      const fallbackExtent =
        axis === "x"
          ? Math.max(280, window.innerWidth * 0.82)
          : Math.max(360, window.innerHeight * 0.55);

      startRef.current = {
        pointerId: event.pointerId,
        coordinate: coordinateFor(event, axis),
        startedAt: performance.now(),
        extent: measuredExtent > 0 ? measuredExtent : fallbackExtent,
      };

      event.currentTarget.setPointerCapture?.(event.pointerId);
      clearDismissTimer();
      setOffset(0);
      setInteracted(true);
      setDismissing(false);
      setDragging(true);
    },
    [axis, canStart, clearDismissTimer],
  );

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      const start = startRef.current;
      if (!start || start.pointerId !== event.pointerId) return;

      setOffset(
        directedDistance(
          start.coordinate,
          coordinateFor(event, axis),
          direction,
        ),
      );
    },
    [axis, direction],
  );

  const finishPointer = useCallback(
    (event: ReactPointerEvent<HTMLElement>, cancelled = false) => {
      const start = startRef.current;
      if (!start || start.pointerId !== event.pointerId) return;

      const distance = directedDistance(
        start.coordinate,
        coordinateFor(event, axis),
        direction,
      );
      const elapsed = Math.max(1, performance.now() - start.startedAt);
      const threshold = Math.max(
        MIN_DISTANCE_PX,
        Math.min(MAX_DISTANCE_PX, start.extent * 0.28),
      );
      const isFling =
        elapsed >= MIN_FLING_DURATION_MS &&
        distance / elapsed >= FLING_VELOCITY_PX_MS;

      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
      startRef.current = null;
      setDragging(false);

      if (!cancelled && (distance >= threshold || isFling)) {
        setDismissing(true);
        setOffset(start.extent + 32);
        dismissTimerRef.current = window.setTimeout(
          onDismiss,
          DISMISS_DURATION_MS,
        );
        return;
      }

      window.setTimeout(() => setOffset(0), 0);
    },
    [axis, direction, onDismiss],
  );

  const onPointerUp = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => finishPointer(event),
    [finishPointer],
  );

  const onPointerCancel = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => finishPointer(event, true),
    [finishPointer],
  );

  const extent = startRef.current?.extent ?? 1;
  const progress = Math.min(1, offset / extent);

  return {
    offset,
    progress,
    dragging,
    interacted,
    dismissing,
    reset,
    pointerHandlers: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel,
    },
  };
}
