import type { VesselPhotoResponse, VesselV1 } from "../../api/contract";
import { trackingIdentity } from "../../api/trackingClient";
import { BottomSheetFrame } from "../../components/BottomSheetFrame";
import {
  TrackingToggle,
  type TrackingControls,
} from "../tracking/TrackingToggle";

type VesselSheetProps = {
  vessel: VesselV1;
  open: boolean;
  onClose: () => void;
  photo?: VesselPhotoResponse | null;
  photoLoading?: boolean;
  photoError?: "temporary" | null;
  trackingControls?: TrackingControls;
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
  photoError = null,
  trackingControls,
}: VesselSheetProps) {
  return (
    <BottomSheetFrame
      open={open}
      onClose={onClose}
      ariaLabel={`Ficha do navio ${vessel.name}`}
      closeLabel="Fechar ficha do navio"
    >
      <header className="vessel-sheet__header">
        <div>
          <p className="vessel-sheet__eyebrow">Ficha do navio</p>
          <h2>{vessel.name}</h2>
        </div>
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
                <a href={photo.source_url} target="_blank" rel="noreferrer">
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
      ) : photoError === "temporary" ? (
        <p className="vessel-sheet__photo-status" role="status">
          Foto temporariamente indisponível.
        </p>
      ) : photo ? (
        <p className="vessel-sheet__photo-status" role="status">
          Sem foto disponível para este navio.
        </p>
      ) : null}

      {trackingControls ? (
        <TrackingToggle
          controls={trackingControls}
          target={{
            vessel_identity: trackingIdentity(vessel.imo, vessel.name),
            vessel_imo: vessel.imo,
            vessel_name: vessel.name,
          }}
        />
      ) : null}

      <dl className="vessel-sheet__details">
        <Detail label="IMO" value={vessel.imo} />
        <Detail label="Situação" value={vessel.status} />
        <Detail label="POB" value={vessel.pob} />
        <Detail
          label="Local"
          value={
            vessel.berth
              ? `Berço ${vessel.berth}${vessel.side ? ` / ${vessel.side}` : ""}`
              : null
          }
        />
        <Detail label="ETA" value={vessel.eta} />
        <Detail label="ETB/ETS" value={vessel.etb_ets} />
        <Detail label="Origem" value={vessel.origin_port} />
        <Detail label="Agência" value={vessel.agency} />
        <Detail label="Rebocadores" value={vessel.tugs} />
        <Detail label="IRIN" value={vessel.irin} />
        <Detail label="Bandeira" value={vessel.flag} />
      </dl>
    </BottomSheetFrame>
  );
}
