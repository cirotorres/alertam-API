import pkg from "../../package.json";
import { useShellContext } from "../app/AppShell";
import type { DevicePlatform } from "../features/pairing/devicePlatform";
import { usePush } from "../features/push/PushProvider";


const PREFERENCE_LABELS = [
  ["confirmed", "Confirmações"],
  ["updated", "Atualizações"],
  ["completed", "Conclusões"],
  ["cancelled", "Cancelamentos"],
] as const;

function platformLabel(platform: DevicePlatform): string {
  if (platform === "ios") return "iPhone/iPad";
  if (platform === "android") return "Android";
  return "Outro aparelho";
}


export function ConfigPage() {
  const {
    pairing,
    installation,
    snapshotState,
    onPairingCleared,
    demoMode,
  } = useShellContext();
  const push = usePush();

  const forget = async () => {
    if (!window.confirm(
      "Esquecer este aparelho? Será necessário escanear um novo QR Code.",
    )) {
      return;
    }

    if (!demoMode) {
      try {
        await push.disablePush();
      } catch {
        // Remote/browser Push cleanup is best-effort.
      }
    }

    onPairingCleared();
  };

  const installationLabel = installation
    ? `${platformLabel(installation.platform)} · ${installation.displayCode}`
    : "Não identificado";

  return (
    <section className="page-stack">
      <h1>Config.</h1>
      {demoMode ? (
        <p className="demo-note">
          Configuração ilustrativa: nenhum pareamento real é alterado neste modo.
        </p>
      ) : null}
      <dl className="settings-list">
        <div>
          <dt>Este aparelho</dt>
          <dd>{installationLabel}</dd>
        </div>
        <div>
          <dt>AlertaM conectado</dt>
          <dd>{pairing.deviceId}</dd>
        </div>
        <div>
          <dt>Última sincronização</dt>
          <dd>{snapshotState.data?.meta.received_at ?? "Aguardando"}</dd>
        </div>
        <div><dt>Versão</dt><dd>{pkg.version}</dd></div>
        <div>
          <dt>Instalação PWA</dt>
          <dd>Disponibilidade detectada pelo dispositivo</dd>
        </div>
      </dl>
      {!demoMode ? (
        <section
          className="push-settings"
          aria-labelledby="push-settings-title"
        >
          <h2 id="push-settings-title">Notificações</h2>
          {!push.supported ? (
            <p>
              Notificações push não são suportadas neste navegador.
            </p>
          ) : push.permission === "denied" ? (
            <p>
              A permissão de notificações está bloqueada. Ative-a nas
              configurações do navegador para continuar.
            </p>
          ) : (
            <>
              <button
                className="settings-action"
                type="button"
                onClick={() => void (
                  push.active
                    ? push.disablePush()
                    : push.enablePush()
                )}
              >
                {push.active
                  ? "Desativar notificações"
                  : "Ativar notificações"}
              </button>
              {push.active ? (
                <fieldset className="push-preferences">
                  <legend>Tipos de alerta</legend>
                  {PREFERENCE_LABELS.map(([key, label]) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={push.preferences[key]}
                        onChange={(event) => void push.updatePreference(
                          key,
                          event.currentTarget.checked,
                        )}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </fieldset>
              ) : null}
            </>
          )}
          {push.error ? (
            <p className="settings-error" role="alert">
              {push.error}
            </p>
          ) : null}
        </section>
      ) : null}
      {!demoMode ? (
        <button
          className="danger-button"
          type="button"
          onClick={() => void forget()}
        >
          Esquecer este aparelho
        </button>
      ) : null}
    </section>
  );
}
