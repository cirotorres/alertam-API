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

export function StatusCards({ status, data }: StatusCardsProps) {
  const state = LABELS[status];
  return (
    <section className={`status-card status-card--${state.tone}`} role="status">
      <div>
        <strong>{state.title}</strong>
        <p>{state.detail}</p>
      </div>
      {data ? <span>{data.meta.age_seconds}s desde o recebimento</span> : null}
    </section>
  );
}
