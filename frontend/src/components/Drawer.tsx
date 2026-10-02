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

type DrawerIconKind =
  | "map"
  | "alerts"
  | "history"
  | "tracked"
  | "settings"
  | "install"
  | "about";

function DrawerIcon({ kind }: { kind: DrawerIconKind }) {
  const content = (() => {
    switch (kind) {
      case "map":
        return (
          <>
            <path d="M3.5 6.5 8.5 4l7 2.5 5-2.5v13.5l-5 2.5-7-2.5-5 2.5V6.5Z" />
            <path d="M8.5 4v13.5M15.5 6.5V20" />
          </>
        );
      case "alerts":
        return (
          <>
            <path d="M18 8.5a6 6 0 0 0-12 0c0 5.8-2.5 6.5-2.5 6.5h17S18 14.3 18 8.5Z" />
            <path d="M9.5 18a2.7 2.7 0 0 0 5 0" />
          </>
        );
      case "history":
        return (
          <>
            <path d="M4.2 8.5A8.2 8.2 0 1 1 4 15" />
            <path d="M4.2 4.5v4h4M12 7.5V12l3 2" />
          </>
        );
      case "tracked":
        return (
          <>
            <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
            <circle cx="12" cy="12" r="2.6" />
          </>
        );
      case "settings":
        return (
          <>
            <circle cx="12" cy="12" r="3" />
            <path d="M19 13.5v-3l-2-.7a7.5 7.5 0 0 0-.7-1.7l.9-1.9-2.1-2.1-1.9.9a7.5 7.5 0 0 0-1.7-.7L10.5 2h-3l-.7 2.3a7.5 7.5 0 0 0-1.7.7l-1.9-.9-2.1 2.1.9 1.9a7.5 7.5 0 0 0-.7 1.7L2 10.5v3l2 .7c.2.6.4 1.2.7 1.7l-.9 1.9 2.1 2.1 1.9-.9c.5.3 1.1.5 1.7.7l.7 2.3h3l.7-2.3c.6-.2 1.2-.4 1.7-.7l1.9.9 2.1-2.1-.9-1.9c.3-.5.5-1.1.7-1.7l1.6-.7Z" transform="translate(1.5 0) scale(.875)" />
          </>
        );
      case "install":
        return (
          <>
            <path d="M12 3v11M8 10l4 4 4-4" />
            <path d="M5 18v2h14v-2" />
          </>
        );
      case "about":
        return (
          <>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 10.5V17M12 7h.01" />
          </>
        );
    }
  })();

  return (
    <svg
      className="drawer__item-icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {content}
    </svg>
  );
}


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
              <Link ref={firstLinkRef} to={routePath("")} onClick={onClose}>
                <DrawerIcon kind="map" />
                <span>Mapa</span>
              </Link>
              <Link to={routePath("/alertas")} onClick={onClose}>
                <DrawerIcon kind="alerts" />
                <span>Alertas</span>
              </Link>
              <Link to={routePath("/historico")} onClick={onClose}>
                <DrawerIcon kind="history" />
                <span>Histórico</span>
              </Link>
              <Link to={routePath("/acompanhados")} onClick={onClose}>
                <DrawerIcon kind="tracked" />
                <span>Acompanhados</span>
              </Link>
              <Link to={routePath("/config")} onClick={onClose}>
                <DrawerIcon kind="settings" />
                <span>Configurações</span>
              </Link>
            </nav>
            <div className="drawer__separator" />
            <button
              type="button"
              disabled={pwa.state === "installed"}
              onClick={() => void handleInstall()}
            >
              <DrawerIcon kind="install" />
              <span>
                {pwa.state === "installed" ? "Aplicativo instalado" : "Instalar aplicativo"}
              </span>
            </button>
            <Link to={routePath("/sobre")} onClick={onClose}>
              <DrawerIcon kind="about" />
              <span>Sobre</span>
            </Link>
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
