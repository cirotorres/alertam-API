import type {
  TrackedVessel,
  TrackingTarget,
} from "../../api/trackingClient";

export type TrackingControls = {
  findTracking: (target: TrackingTarget | string) => TrackedVessel | null;
  mutationPending: boolean;
  mutationError: string | null;
  startTracking: (target: TrackingTarget) => Promise<boolean>;
  stopTracking: (trackedVesselId: string) => Promise<boolean>;
  clearMutationError: () => void;
};

export function TrackingToggle({
  target,
  controls,
}: {
  target: TrackingTarget;
  controls: TrackingControls;
}) {
  const tracked = controls.findTracking(target);

  const toggle = () => {
    controls.clearMutationError();
    if (tracked) {
      void controls.stopTracking(tracked.tracked_vessel_id);
    } else {
      void controls.startTracking(target);
    }
  };

  return (
    <section className="tracking-toggle" aria-label="Acompanhamento do navio">
      <button
        type="button"
        className="tracking-toggle__button"
        disabled={controls.mutationPending}
        onClick={toggle}
      >
        {controls.mutationPending
          ? "Salvando…"
          : tracked
            ? "★ Acompanhando · Parar"
            : "☆ Acompanhar navio"}
      </button>
      {target.vessel_imo === null ? (
        <small className="tracking-toggle__note">
          Sem IMO: identificação por nome exato enquanto o IMO não estiver disponível.
        </small>
      ) : null}
      {controls.mutationError ? (
        <p className="tracking-toggle__error" role="alert">
          {controls.mutationError}
        </p>
      ) : null}
    </section>
  );
}
