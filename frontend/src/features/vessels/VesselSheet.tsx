import { useCallback, useEffect } from "react";

import type { VesselV1 } from "../../api/contract";
import { useDismissDrag } from "../../hooks/useDismissDrag";

type VesselSheetProps = {
  vessel: VesselV1;
  open: boolean;
  onClose: () => void;
  imageUrl?: string;
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
  imageUrl,
}: VesselSheetProps) {
  const canStartDrag = useCallback((target: EventTarget | null) => {
    return (
      target instanceof Element &&
      target.closest(".vessel-sheet__drag-zone") !== null
    );
  }, []);
  const drag = useDismissDrag({
    axis: "y",
    direction: "positive",
    onDismiss: onClose,
    canStart: canStartDrag,
  });

  useEffect(() => {
    if (open) drag.reset();
  }, [open]);

  const dragActive = drag.interacted && (open || drag.dismissing);
  const sheetStyle = dragActive
    ? {
        transform: `translate(-50%, ${drag.offset}px)`,
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
        className={`vessel-sheet ${open ? "is-open" : "is-closing"} ${dragClasses}`}
        style={sheetStyle}
        role="dialog"
        aria-modal="true"
        aria-hidden={!open}
        aria-label={`Ficha do navio ${vessel.name}`}
        {...drag.pointerHandlers}
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
      {imageUrl ? <img className="vessel-sheet__photo" src={imageUrl} alt="" /> : null}
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
