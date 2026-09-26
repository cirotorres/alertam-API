import { useShellContext } from "../app/AppShell";
import { recentAlerts } from "../features/vessels/projections";

export function AlertsPage() {
  const { snapshotState } = useShellContext();
  const items = snapshotState.data
    ? recentAlerts(snapshotState.data.snapshot)
    : [];

  return (
    <section className="page-stack">
      <h1>Alertas</h1>
      <p className="page-intro">Ocorrências operacionais mais recentes do snapshot.</p>
      {items.length === 0 ? (
        <p className="empty-state">Nenhum alerta recente.</p>
      ) : (
        <ol className="timeline">
          {items.map((item) => (
            <li key={item.id}>
              <strong>{item.vessel_name}</strong>
              <span>
                {item.type === "ATRACACAO" ? "Atracação" : "Desatracação"} · Berço {item.berth ?? "—"}
              </span>
              <small>{item.status === "ACTIVE" ? "Confirmada" : "Concluída"}</small>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
