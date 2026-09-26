import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { InstallHelp } from "../features/install/InstallHelp";
import { usePwaInstall } from "../features/install/usePwaInstall";

type DrawerProps = {
  open: boolean;
  onClose: () => void;
  basePath?: string;
  demoMode?: boolean;
};

export function Drawer({
  open,
  onClose,
  basePath = "",
  demoMode = false,
}: DrawerProps) {
  const firstLinkRef = useRef<HTMLAnchorElement>(null);
  const routePath = (suffix: string) =>
    basePath ? `${basePath}${suffix}` : suffix || "/";
  const [installHelpOpen, setInstallHelpOpen] = useState(false);
  const [rendered, setRendered] = useState(open);
  const pwa = usePwaInstall();

  useEffect(() => {
    if (open) {
      setRendered(true);
      return;
    }
    if (!rendered) return;

    const timeoutId = window.setTimeout(() => setRendered(false), 220);
    return () => window.clearTimeout(timeoutId);
  }, [open, rendered]);

  useEffect(() => {
    if (!open) return;
    firstLinkRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!rendered && !installHelpOpen) return null;
  const handleInstall = async () => {
    if (pwa.state === "installed") return;
    if (pwa.state === "available") {
      await pwa.install();
      onClose();
      return;
    }
    setInstallHelpOpen(true);
    onClose();
  };

  return (
    <>
      {rendered ? (
        <>
          <button
            type="button"
            className={`drawer-overlay ${open ? "is-open" : "is-closing"}`}
            aria-label="Fechar menu"
            aria-hidden={!open}
            disabled={!open}
            onClick={onClose}
          />
          <aside
            className={`drawer ${open ? "is-open" : "is-closing"}`}
            role="dialog"
            aria-modal="true"
            aria-hidden={!open}
            aria-label="Menu principal"
          >
            <div className="drawer__brand">
              <strong>AlertaM</strong>
              <span>{demoMode ? "Modo demonstração" : "Consulta mobile"}</span>
            </div>
            <nav aria-label="Navegação principal">
              <Link ref={firstLinkRef} to={routePath("")} onClick={onClose}>Mapa</Link>
              <Link to={routePath("/alertas")} onClick={onClose}>Alertas</Link>
              <Link to={routePath("/historico")} onClick={onClose}>Histórico</Link>
              <Link to={routePath("/config")} onClick={onClose}>Config.</Link>
            </nav>
            <div className="drawer__separator" />
            <button
              type="button"
              disabled={pwa.state === "installed"}
              onClick={() => void handleInstall()}
            >
              {pwa.state === "installed" ? "Aplicativo instalado" : "Instalar aplicativo"}
            </button>
            <Link to={routePath("/sobre")} onClick={onClose}>Sobre</Link>
          </aside>
        </>
      ) : null}
      <InstallHelp
        open={installHelpOpen}
        state={pwa.state}
        onClose={() => setInstallHelpOpen(false)}
      />
    </>
  );
}
