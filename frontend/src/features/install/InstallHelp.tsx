import type { PwaInstallState } from "./usePwaInstall";

type InstallHelpProps = {
  open: boolean;
  state: PwaInstallState;
  onClose: () => void;
};

export function InstallHelp({ open, state, onClose }: InstallHelpProps) {
  if (!open) return null;

  const message =
    state === "ios"
      ? "No Safari, toque em Compartilhar e escolha Adicionar à Tela de Início."
      : "A instalação como aplicativo não está disponível neste navegador.";

  return (
    <div className="install-help" role="dialog" aria-modal="true" aria-label="Instalar aplicativo">
      <h2>Instalar AlertaM</h2>
      <p>{message}</p>
      <button type="button" onClick={onClose}>Fechar</button>
    </div>
  );
}
