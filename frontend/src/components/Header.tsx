import type { RefObject } from "react";
import type { SnapshotStatus } from "../features/snapshot/useSnapshotPolling";

type HeaderProps = {
  status: SnapshotStatus;
  lastCollectionAt: string | null;
  demoMode?: boolean;
  onMenu: () => void;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
};

function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
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
        <span aria-hidden="true">☰</span>
      </button>

      <div className="mobile-header__identity">
        <strong>Alerta de Movimentações Marítimas</strong>
        <div className="mobile-header__status">
          <span
            className="mobile-header__session"
            data-demo={demoMode ? "true" : "false"}
          >
            {sessionText}
          </span>
          <span className="mobile-header__separator" aria-hidden="true">|</span>
          <span>
            Última leitura: <time>{formatTime(lastCollectionAt)}</time>
          </span>
        </div>
      </div>
    </header>
  );
}
