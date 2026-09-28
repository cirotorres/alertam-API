import { useCallback, useEffect, useRef, useState } from "react";

import type { VesselPhotoResponse, VesselV1 } from "../../api/contract";
import { useDismissDrag } from "../../hooks/useDismissDrag";

type VesselSheetProps = {
  vessel: VesselV1;
  open: boolean;
  onClose: () => void;
  photo?: VesselPhotoResponse | null;
  photoLoading?: boolean;
};

function Detail({ label, value }: { label: string; value: string | number | null }) {
  if (value === null || value === "") return null;
  return (
    <div className="vessel-sheet__detail">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function VesselSheet({
  vessel,
  open,
  onClose,
  photo = null,
  photoLoading = false,
}: VesselSheetProps) {
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
    if (open) {
      drag.reset();
      setUpwardPull(0);
      touchStartYRef.current = null;
      touchScrollModeRef.current = false;
      dragFromHandleRef.current = false;
    }
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
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <button
        className={`vessel-sheet-backdrop ${open ? "is-open" : "is-closing"} ${dragClasses}`}
        style={backdropStyle}
        type="button"
        aria-label="Fechar ficha"
        aria-hidden={!open}
        disabled={!open}
        onClick={onClose}
      />
      <aside
        className={`vessel-sheet ${open ? "is-open" : "is-closing"} ${atScrollTop ? "is-at-scroll-top" : ""} ${dragClasses}`}
        style={sheetStyle}
        role="dialog"
        aria-modal="true"
        aria-hidden={!open}
        aria-label={`Ficha do navio ${vessel.name}`}
        onPointerDown={(event) => {
          if (
            event.pointerType === "touch" &&
            canStartDrag(event.target, event.currentTarget)
          ) {
            touchStartYRef.current = event.clientY;
            touchScrollModeRef.current = false;
            dragFromHandleRef.current = Boolean(
              event.target instanceof Element &&
              event.target.closest(".vessel-sheet__drag-zone"),
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
        <div className="vessel-sheet__drag-zone" aria-hidden="true">
          <div className="vessel-sheet__handle" />
        </div>
      <header className="vessel-sheet__header">
        <div>
          <p className="vessel-sheet__eyebrow">Ficha do navio</p>
          <h2>{vessel.name}</h2>
        </div>
        <button
          type="button"
          autoFocus
          onClick={onClose}
          aria-label="Fechar ficha do navio"
        >
          ×
        </button>
      </header>
      {photo?.photo_url ? (
        <figure className="vessel-sheet__photo-wrap">
          <img
            className="vessel-sheet__photo"
            src={photo.photo_url}
            alt={`Foto de ${vessel.name}`}
            loading="eager"
          />
          <figcaption className="vessel-sheet__photo-credit">
            Foto{photo.author ? `: ${photo.author}` : ""}
            {photo.license ? ` · ${photo.license}` : ""}
            {photo.source_url ? (
              <>
                {" · "}
                <a
                  href={photo.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Wikimedia Commons
                </a>
              </>
            ) : (
              " · Wikimedia Commons"
            )}
          </figcaption>
        </figure>
      ) : photoLoading ? (
        <p className="vessel-sheet__photo-status" role="status">
          Buscando foto…
        </p>
      ) : null}
      <dl className="vessel-sheet__details">
        <Detail label="IMO" value={vessel.imo} />
        <Detail label="Situação" value={vessel.status} />
        <Detail label="POB" value={vessel.pob} />
        <Detail label="Local" value={vessel.berth ? `Berço ${vessel.berth}${vessel.side ? ` / ${vessel.side}` : ""}` : null} />
        <Detail label="ETA" value={vessel.eta} />
        <Detail label="ETB/ETS" value={vessel.etb_ets} />
        <Detail label="Origem" value={vessel.origin_port} />
        <Detail label="Agência" value={vessel.agency} />
        <Detail label="Rebocadores" value={vessel.tugs} />
        <Detail label="IRIN" value={vessel.irin} />
        <Detail label="Bandeira" value={vessel.flag} />
      </dl>
      </aside>
    </>
  );
}
