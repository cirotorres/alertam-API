import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { InstallHelp } from "../features/install/InstallHelp";
import { usePwaInstall } from "../features/install/usePwaInstall";
import { useDismissDrag } from "../hooks/useDismissDrag";

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
  const canStartDrag = useCallback((target: EventTarget | null) => {
    return !(
      target instanceof Element &&
      target.closest("a, button, input, select, textarea")
    );
  }, []);
  const drag = useDismissDrag({
    axis: "x",
    direction: "negative",
    onDismiss: onClose,
    canStart: canStartDrag,
  });

  useEffect(() => {
    if (open) {
      drag.reset();
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

  const dragActive = drag.interacted && (open || drag.dismissing);
  const drawerStyle = dragActive
    ? {
        transform: `translateX(-${drag.offset}px)`,
        transition: drag.dragging
          ? "none"
          : "transform 180ms cubic-bezier(0.22, 1, 0.36, 1)",
      }
    : undefined;
  const overlayStyle = dragActive
    ? {
        opacity: Math.max(0, 1 - drag.progress * 0.92),
        transition: drag.dragging ? "none" : "opacity 180ms ease-out",
      }
    : undefined;
  const dragClasses = [
    drag.interacted ? "is-drag-interacted" : "",
    drag.dragging ? "is-dragging" : "",
    drag.dismissing ? "is-drag-dismissing" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      {rendered ? (
        <>
          <button
            type="button"
            className={`drawer-overlay ${open ? "is-open" : "is-closing"} ${dragClasses}`}
            style={overlayStyle}
            aria-label="Fechar menu"
            aria-hidden={!open}
            disabled={!open}
            onClick={onClose}
          />
          <aside
            className={`drawer ${open ? "is-open" : "is-closing"} ${dragClasses}`}
            style={drawerStyle}
            role="dialog"
            aria-modal="true"
            aria-hidden={!open}
            aria-label="Menu principal"
            {...drag.pointerHandlers}
          >
            <div className="drawer__grab" aria-hidden="true" />
            <div className="drawer__brand">
              <strong>AlertaM</strong>
              <span>{demoMode ? "Modo demonstração" : "Consulta mobile"}</span>
            </div>
            <nav aria-label="Navegação principal">
              <Link ref={firstLinkRef} to={routePath("")} onClick={onClose}>Mapa</Link>
              <Link to={routePath("/alertas")} onClick={onClose}>Alertas</Link>
              <Link to={routePath("/historico")} onClick={onClose}>Histórico</Link>
              <Link to={routePath("/acompanhados")} onClick={onClose}>Acompanhados</Link>
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
