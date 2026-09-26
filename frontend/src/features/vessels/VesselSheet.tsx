import type { VesselV1 } from "../../api/contract";

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
  return (
    <aside
      className={`vessel-sheet ${open ? "is-open" : "is-closing"}`}
      role="dialog"
      aria-modal="true"
      aria-hidden={!open}
      aria-label={`Ficha do navio ${vessel.name}`}
    >
      <div className="vessel-sheet__handle" aria-hidden="true" />
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
  );
}
