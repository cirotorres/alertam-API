import { useShellContext } from "../app/AppShell";
import { maneuverHistory } from "../features/vessels/projections";

export function HistoryPage() {
  const { snapshotState } = useShellContext();
  const items = snapshotState.data
    ? maneuverHistory(snapshotState.data.snapshot)
    : [];

  return (
    <section className="page-stack">
      <h1>Histórico</h1>
      <p className="page-intro">Timeline recente de manobras confirmadas e concluídas.</p>
      {items.length === 0 ? (
        <p className="empty-state">Nenhuma manobra no histórico recente.</p>
      ) : (
        <ol className="timeline">
          {items.map((item) => (
            <li key={item.id}>
              <strong>{item.vessel_name}</strong>
              <span>{item.type === "ATRACACAO" ? "Atracação" : "Desatracação"} · Berço {item.berth ?? "—"}</span>
              <small>{item.completed_at ?? item.detected_at}</small>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
