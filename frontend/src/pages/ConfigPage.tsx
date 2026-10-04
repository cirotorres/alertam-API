import { useState } from "react";

import pkg from "../../package.json";
import { useShellContext } from "../app/AppShell";
import { BottomSheetFrame } from "../components/BottomSheetFrame";
import { PairingConnectPanel } from "../features/pairing/PairingConnectPanel";
import type { DevicePlatform } from "../features/pairing/devicePlatform";
import { usePush } from "../features/push/PushProvider";


const PREFERENCE_LABELS = [
  ["confirmed", "Confirmações"],
  ["updated", "Atualizações"],
  ["completed", "Conclusões"],
  ["cancelled", "Cancelamentos"],
  ["anchored", "Entradas no fundeio"],
] as const;

function platformLabel(platform: DevicePlatform): string {
  if (platform === "ios") return "iPhone/iPad";
  if (platform === "android") return "Android";
  return "Outro aparelho";
}

function formatSynchronization(value: string | null | undefined): string {
  if (!value) return "Aguardando";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
    .format(date)
    .replace(",", " ·");
}


export function ConfigPage() {
  const {
    pairing,
    installation,
    snapshotState,
    onPairingCleared,
    onPairingCandidate,
    demoMode,
  } = useShellContext();
  const push = usePush();
  const [switchOpen, setSwitchOpen] = useState(false);

  const forget = async () => {
    if (!window.confirm(
      "Esquecer este aparelho? Será necessário conectar novamente por QR Code ou código de conexão.",
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
    <section className="page-stack page-stack--with-bottom-nav">
      <h1>Configurações</h1>
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
          <dd>{formatSynchronization(snapshotState.data?.meta.received_at)}</dd>
        </div>
        <div><dt>Versão</dt><dd>{pkg.version}</dd></div>
        <div>
          <dt>Instalação PWA</dt>
          <dd>Disponibilidade detectada pelo dispositivo</dd>
        </div>
      </dl>
      {!demoMode ? (
        <section className="pairing-switch-settings">
          <h2>Conexão</h2>
          <p>
            Troque o AlertaM deste PWA sem apagar ou reinstalar o aplicativo.
          </p>
          <button
            className="settings-action"
            type="button"
            onClick={() => setSwitchOpen(true)}
          >
            Trocar AlertaM
          </button>
        </section>
      ) : null}
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
      {switchOpen ? (
        <BottomSheetFrame
          open
          onClose={() => setSwitchOpen(false)}
          ariaLabel="Trocar AlertaM"
          closeLabel="Fechar troca de AlertaM"
        >
          <div className="pairing-switch-sheet">
            <h2>Trocar AlertaM</h2>
            <p>
              Leia o QR Code do novo Desktop ou use o código de 6 dígitos.
            </p>
            <PairingConnectPanel
              onCandidate={(candidate) => {
                setSwitchOpen(false);
                onPairingCandidate(candidate);
              }}
            />
          </div>
        </BottomSheetFrame>
      ) : null}
    </section>
  );
}
