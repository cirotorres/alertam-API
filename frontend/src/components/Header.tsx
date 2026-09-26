import type { RefObject } from "react";
import type { SnapshotStatus } from "../features/snapshot/useSnapshotPolling";

type HeaderProps = {
  status: SnapshotStatus;
  lastCollectionAt: string | null;
  demoMode?: boolean;
  onMenu: () => void;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
};

function formatDateTime(value: string | null): string {
  if (!value) return "Aguardando leitura";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

export function Header({
  status,
  lastCollectionAt,
  demoMode = false,
  onMenu,
  menuButtonRef,
}: HeaderProps) {
  const sessionText = demoMode
    ? "Modo demonstração"
    : status === "revoked"
      ? "Acesso revogado"
      : "Sessão válida";

  return (
    <header className="mobile-header">
      <button
        ref={menuButtonRef}
        type="button"
        className="mobile-header__menu"
        aria-label="Abrir menu"
        onClick={onMenu}
      >
        ☰
      </button>
      <div className="mobile-header__identity">
        <strong>AlertaM</strong>
        <span>Alerta de Movimentações Marítimas</span>
      </div>
      <div className="mobile-header__status">
        <span>{sessionText}</span>
        <time>{formatDateTime(lastCollectionAt)}</time>
      </div>
    </header>
  );
}
