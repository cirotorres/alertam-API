import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

type DrawerProps = {
  open: boolean;
  onClose: () => void;
  onInstall: () => void;
};

export function Drawer({ open, onClose, onInstall }: DrawerProps) {
  const firstLinkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;
    firstLinkRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <>
      <button
        type="button"
        className="drawer-overlay"
        aria-label="Fechar menu"
        onClick={onClose}
      />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Menu principal">
        <div className="drawer__brand">
          <strong>AlertaM</strong>
          <span>Consulta mobile</span>
        </div>
        <nav aria-label="Navegação principal">
          <Link ref={firstLinkRef} to="/" onClick={onClose}>Mapa</Link>
          <Link to="/alertas" onClick={onClose}>Alertas</Link>
          <Link to="/historico" onClick={onClose}>Histórico</Link>
          <Link to="/config" onClick={onClose}>Config.</Link>
        </nav>
        <div className="drawer__separator" />
        <button type="button" onClick={() => { onInstall(); onClose(); }}>
          Instalar aplicativo
        </button>
        <Link to="/sobre" onClick={onClose}>Sobre</Link>
      </aside>
    </>
  );
}
