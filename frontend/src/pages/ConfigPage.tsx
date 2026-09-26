import pkg from "../../package.json";
import { useShellContext } from "../app/AppShell";
import { clearPairing } from "../features/pairing/pairingStorage";

export function ConfigPage() {
  const { pairing, snapshotState, onPairingCleared } = useShellContext();

  const forget = () => {
    if (!window.confirm("Esquecer este aparelho? Será necessário escanear um novo QR Code.")) {
      return;
    }
    clearPairing();
    onPairingCleared();
  };

  return (
    <section className="page-stack">
      <h1>Config.</h1>
      <dl className="settings-list">
        <div><dt>Dispositivo</dt><dd>{pairing.deviceId}</dd></div>
        <div><dt>Última sincronização</dt><dd>{snapshotState.data?.meta.received_at ?? "Aguardando"}</dd></div>
        <div><dt>Versão</dt><dd>{pkg.version}</dd></div>
        <div><dt>Instalação PWA</dt><dd>Disponibilidade detectada pelo dispositivo</dd></div>
      </dl>
      <button className="danger-button" type="button" onClick={forget}>
        Esquecer este aparelho
      </button>
    </section>
  );
}
