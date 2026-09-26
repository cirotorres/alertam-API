import type { SnapshotReadResponse } from "../api/contract";
import type { SnapshotStatus } from "../features/snapshot/useSnapshotPolling";

type StatusCardsProps = {
  status: SnapshotStatus;
  data: SnapshotReadResponse | null;
};

const LABELS: Record<SnapshotStatus, { title: string; detail: string; tone: string }> = {
  loading: { title: "Carregando dados", detail: "Consultando o AlertaM.", tone: "neutral" },
  online: { title: "Sistema ativo", detail: "Monitorando movimentações marítimas.", tone: "positive" },
  stale: { title: "Dados desatualizados", detail: "O coletor não envia uma leitura recente.", tone: "warning" },
  waiting: { title: "Aguardando primeira leitura", detail: "O pareamento está válido, mas ainda não há snapshot.", tone: "neutral" },
  offline: { title: "Sem conexão com o servidor", detail: "Exibindo a última leitura disponível quando possível.", tone: "warning" },
  revoked: { title: "Acesso expirado ou revogado", detail: "Escaneie um novo QR Code no AlertaM Desktop.", tone: "danger" },
  unsupported: { title: "Atualização necessária", detail: "Esta versão do AlertaM Mobile precisa ser atualizada.", tone: "danger" },
};

function formatReadAt(value: string | null): { time: string; date: string } {
  if (!value) return { time: "—", date: "—" };
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { time: value, date: "" };

  return {
    time: new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date),
    date: new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(date),
  };
}

export function StatusCards({ status, data }: StatusCardsProps) {
  const state = LABELS[status];
  const readAt = formatReadAt(
    data?.snapshot.collector.last_collection_at ?? null,
  );

  return (
    <section className="status-stack" role="status">
      <article className="reading-card">
        <span className="reading-card__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" role="presentation">
            <circle cx="12" cy="12" r="8.5" />
            <path d="M12 7v5l3.5 2" />
          </svg>
        </span>
        <div>
          <span className="reading-card__label">Última leitura</span>
          <strong>
            {readAt.time}
            {readAt.date ? <> · {readAt.date}</> : null}
          </strong>
        </div>
      </article>

      <article className={`system-card system-card--${state.tone}`}>
        <span className="system-card__dot" aria-hidden="true" />
        <div>
          <strong>{state.title}</strong>
          <p>{state.detail}</p>
        </div>
      </article>
    </section>
  );
}
