import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AccessRevokedError,
  TemporaryApiError,
} from "../../api/snapshotClient";
import {
  clearInstallationId,
  createFreshInstallationId,
  loadInstallationId,
  storeInstallationId,
} from "../push/installationId";
import {
  detectDevicePlatform,
  type DevicePlatform,
} from "./devicePlatform";
import {
  clearInstallationMetadata,
  loadInstallationMetadata,
  storeInstallationMetadata,
} from "./installationMetadata";
import {
  clearPairingFragment,
  parsePairingFragment,
  type Pairing,
} from "./pairing";
import {
  blockSessionRecovery,
  clearPairing,
  clearSessionRecoveryBlock,
  isSessionRecoveryBlocked,
  loadPairing,
  savePairing,
} from "./pairingStorage";
import {
  clearMobileSession,
  createMobileSession,
  recoverMobileSession,
  switchMobileSession,
  validatePairingCandidate,
  type MobileSessionDraft,
  type MobileSessionInfo,
} from "./mobileSessionClient";
import { PairingConnectPanel } from "./PairingConnectPanel";

type GateMode =
  | "idle"
  | "validating"
  | "temporary"
  | "invalid"
  | "confirm-switch"
  | "temporary-switch"
  | "revoked"
  | "disconnected";

type SessionCreator = (
  pairing: Pairing,
  options?: {
    installationId?: string;
    platform?: DevicePlatform;
  },
) => Promise<MobileSessionInfo>;

type SessionRecoverer = () => Promise<{
  pairing: Pairing;
  session: MobileSessionInfo;
} | null>;

type PairingGateProps = {
  candidateValidator?: (
    pairing: Pairing,
  ) => Promise<{ deviceId: string }>;
  sessionCreator?: SessionCreator;
  sessionSwitcher?: (
    pairing: Pairing,
    draft: MobileSessionDraft,
  ) => Promise<MobileSessionInfo>;
  sessionRecoverer?: SessionRecoverer;
  sessionClearer?: () => Promise<void>;
  freshIdFactory?: () => string;
  children: (
    pairing: Pairing,
    resetPairing: () => void,
    sessionReady: boolean,
    handleAccessRevoked: () => void,
    sessionInfo: MobileSessionInfo | null,
    submitPairingCandidate: (pairing: Pairing) => void,
  ) => ReactNode;
};

function persistedSessionFor(
  pairing: Pairing | null,
): MobileSessionInfo | null {
  if (!pairing) {
    return null;
  }
  const metadata = loadInstallationMetadata();
  if (!metadata) {
    return null;
  }
  return {
    deviceId: pairing.deviceId,
    ...metadata,
  };
}

export function PairingGate({
  candidateValidator = validatePairingCandidate,
  sessionCreator = createMobileSession,
  sessionSwitcher = switchMobileSession,
  sessionRecoverer = recoverMobileSession,
  sessionClearer = clearMobileSession,
  freshIdFactory = createFreshInstallationId,
  children,
}: PairingGateProps) {
  const initialPairingRef = useRef<Pairing | null>(loadPairing());
  const [active, setActive] = useState<Pairing | null>(
    initialPairingRef.current,
  );
  const [candidate, setCandidate] = useState<Pairing | null>(null);
  const [mode, setMode] = useState<GateMode>("idle");
  const [sessionInfo, setSessionInfo] = useState<MobileSessionInfo | null>(
    () => persistedSessionFor(initialPairingRef.current),
  );
  const [sessionReady, setSessionReady] = useState(false);

  const skipNextRecoveryRef = useRef(false);
  const syncedSessionRef = useRef<string | null>(null);
  const switchDraftRef = useRef<MobileSessionDraft | null>(null);

  const clearLocalIdentity = useCallback(() => {
    clearPairing();
    clearInstallationId();
    clearInstallationMetadata();
  }, []);

  const resetPairing = useCallback(() => {
    skipNextRecoveryRef.current = true;
    syncedSessionRef.current = null;
    switchDraftRef.current = null;
    clearLocalIdentity();
    blockSessionRecovery();
    void sessionClearer();
    setSessionInfo(null);
    setSessionReady(false);
    setActive(null);
    setCandidate(null);
    setMode("disconnected");
  }, [clearLocalIdentity, sessionClearer]);

  const handleAccessRevoked = useCallback(() => {
    skipNextRecoveryRef.current = true;
    syncedSessionRef.current = null;
    switchDraftRef.current = null;
    clearLocalIdentity();
    blockSessionRecovery();
    void sessionClearer();
    setSessionInfo(null);
    setSessionReady(false);
    setActive(null);
    setCandidate(null);
    setMode("revoked");
  }, [clearLocalIdentity, sessionClearer]);

  const promote = useCallback(
    (
      next: Pairing,
      session: MobileSessionInfo,
    ) => {
      if (next.viewSecret) {
        savePairing(next);
        syncedSessionRef.current =
          `${next.deviceId}:${next.viewSecret}`;
      } else {
        syncedSessionRef.current = null;
      }
      storeInstallationId(session.installationId);
      storeInstallationMetadata({
        installationId: session.installationId,
        displayCode: session.displayCode,
        platform: session.platform,
      });
      switchDraftRef.current = null;
      clearSessionRecoveryBlock();
      setSessionInfo(session);
      setSessionReady(true);
      setActive(
        next.pairingTicket
          ? {
              deviceId: next.deviceId,
              viewSecret: null,
              pairingTicket: null,
              pairedAt: next.pairedAt,
            }
          : next,
      );
      setCandidate(null);
      setMode("idle");
    },
    [],
  );

  const syncActiveSession = useCallback(
    async (current: Pairing) => {
      if (!current.viewSecret) {
        setSessionReady(Boolean(sessionInfo));
        return;
      }

      const installationId = loadInstallationId() ?? undefined;
      const platform =
        loadInstallationMetadata()?.platform ?? detectDevicePlatform();

      setSessionReady(false);
      try {
        const session = await sessionCreator(current, {
          installationId,
          platform,
        });
        syncedSessionRef.current =
          `${current.deviceId}:${current.viewSecret}`;
        setSessionInfo(session);
        setSessionReady(true);
      } catch (error) {
        if (error instanceof AccessRevokedError) {
          handleAccessRevoked();
          return;
        }
        setSessionReady(false);
      }
    },
    [handleAccessRevoked, sessionCreator, sessionInfo],
  );

  const keepActiveAfterCandidateFailure = useCallback(
    (nextMode: "idle" | "temporary") => {
      setMode(nextMode);
      if (active) {
        void syncActiveSession(active);
      }
    },
    [active, syncActiveSession],
  );

  const createCandidateSession = useCallback(
    async (next: Pairing) => {
      const sameDesktop =
        active !== null && active.deviceId === next.deviceId;
      const platform =
        loadInstallationMetadata()?.platform ?? detectDevicePlatform();
      const currentInstallationId = sameDesktop
        ? loadInstallationId()
        : null;

      const createWith = async (
        installationId: string,
      ): Promise<MobileSessionInfo> =>
        sessionCreator(next, {
          installationId,
          platform,
        });

      try {
        if (currentInstallationId) {
          try {
            const session = await createWith(currentInstallationId);
            promote(next, session);
            return;
          } catch (error) {
            if (!(error instanceof AccessRevokedError)) {
              throw error;
            }
          }
        }

        const freshInstallationId = freshIdFactory();
        const session = await createWith(freshInstallationId);
        promote(next, session);
      } catch (error) {
        if (error instanceof AccessRevokedError) {
          setCandidate(null);
          if (active) {
            keepActiveAfterCandidateFailure("idle");
          } else {
            setMode("invalid");
          }
          return;
        }
        setCandidate(next);
        if (active) {
          setSessionReady(false);
        }
        setMode("temporary");
      }
    },
    [
      active,
      freshIdFactory,
      keepActiveAfterCandidateFailure,
      promote,
      sessionCreator,
    ],
  );

  const evaluateCandidate = useCallback(
    async (next: Pairing) => {
      setCandidate(next);
      setMode("validating");

      try {
        const validated = await candidateValidator(next);
        if (validated.deviceId !== next.deviceId) {
          throw new TemporaryApiError();
        }
      } catch (error) {
        if (error instanceof AccessRevokedError) {
          setCandidate(null);
          if (active) {
            keepActiveAfterCandidateFailure("idle");
          } else {
            setMode("invalid");
          }
          return;
        }
        setCandidate(next);
        if (active) {
          setSessionReady(false);
        }
        setMode("temporary");
        return;
      }

      if (active && active.deviceId !== next.deviceId) {
        switchDraftRef.current = null;
        setMode("confirm-switch");
        return;
      }

      await createCandidateSession(next);
    },
    [
      active,
      candidateValidator,
      createCandidateSession,
      keepActiveAfterCandidateFailure,
    ],
  );

  const cancelSwitch = useCallback(() => {
    switchDraftRef.current = null;
    setCandidate(null);
    setMode("idle");
    if (active) {
      void syncActiveSession(active);
    }
  }, [active, syncActiveSession]);

  const executeSwitch = useCallback(async () => {
    if (!active || !candidate) {
      return;
    }

    let draft = switchDraftRef.current;
    if (!draft) {
      draft = {
        installationId: freshIdFactory(),
        platform: detectDevicePlatform(),
        switchId: freshIdFactory(),
      };
      switchDraftRef.current = draft;
    }

    setSessionReady(false);
    try {
      const session = await sessionSwitcher(candidate, draft);
      promote(candidate, session);
    } catch (error) {
      if (error instanceof AccessRevokedError) {
        switchDraftRef.current = null;
        setCandidate(null);
        setMode("idle");
        void syncActiveSession(active);
        return;
      }
      setMode("temporary-switch");
    }
  }, [
    active,
    candidate,
    freshIdFactory,
    promote,
    sessionSwitcher,
    syncActiveSession,
  ]);

  useEffect(() => {
    const hash = window.location.hash;
    if (hash.startsWith("#/pair/")) {
      const parsed = parsePairingFragment(hash);
      clearPairingFragment(window.history);

      if (!parsed) {
        if (active) {
          setMode("idle");
          void syncActiveSession(active);
        } else {
          setMode("invalid");
        }
        return;
      }

      skipNextRecoveryRef.current = false;
      const next: Pairing = {
        deviceId: parsed.deviceId,
        viewSecret: parsed.viewSecret,
        pairedAt: new Date().toISOString(),
      };
      void evaluateCandidate(next);
      return;
    }

    if (active?.viewSecret) {
      const sessionKey = `${active.deviceId}:${active.viewSecret}`;
      if (syncedSessionRef.current !== sessionKey) {
        void syncActiveSession(active);
      }
      return;
    }

    if (active) {
      setSessionReady(Boolean(sessionInfo));
      return;
    }

    if (
      skipNextRecoveryRef.current ||
      isSessionRecoveryBlocked()
    ) {
      return;
    }

    setMode("validating");
    void sessionRecoverer()
      .then((recovered) => {
        if (recovered) {
          promote(recovered.pairing, recovered.session);
        } else {
          setMode("idle");
        }
      })
      .catch(() => setMode("idle"));
  }, [
    active,
    evaluateCandidate,
    promote,
    sessionInfo,
    sessionRecoverer,
    syncActiveSession,
  ]);

  if (mode === "revoked") {
    return (
      <PairingScreen
        title="Acesso revogado"
        detail="Este aparelho não possui mais acesso ao AlertaM. Conecte novamente por QR Code ou código de conexão."
      >
        <PairingConnectPanel
          onCandidate={(next) => void evaluateCandidate(next)}
        />
      </PairingScreen>
    );
  }

  if (mode === "disconnected") {
    return (
      <PairingScreen
        title="Aparelho desconectado"
        detail="Este PWA continua instalado. Conecte-o a um AlertaM por QR Code ou código de conexão."
      >
        <PairingConnectPanel
          onCandidate={(next) => void evaluateCandidate(next)}
        />
      </PairingScreen>
    );
  }

  if (mode === "confirm-switch" && active && candidate) {
    return (
      <PairingScreen
        title="Trocar de AlertaM?"
        detail={`Atual: ${active.deviceId} · Novo: ${candidate.deviceId}`}
      >
        <button type="button" onClick={cancelSwitch}>
          Cancelar
        </button>
        <button type="button" onClick={() => void executeSwitch()}>
          Trocar AlertaM
        </button>
      </PairingScreen>
    );
  }

  if (mode === "temporary-switch" && active && candidate) {
    return (
      <PairingScreen
        title="Troca ainda não confirmada"
        detail="A resposta da troca não chegou. Tente novamente para confirmar o estado sem gerar outro aparelho."
      >
        <button type="button" onClick={() => void executeSwitch()}>
          Tentar novamente
        </button>
      </PairingScreen>
    );
  }

  if (mode === "temporary" && candidate) {
    if (active) {
      return (
        <div className="pairing-switch-state">
          {children(
            active,
            resetPairing,
            sessionReady,
            handleAccessRevoked,
            sessionInfo,
            (next) => void evaluateCandidate(next),
          )}
          <PairingScreen
            title="Não foi possível confirmar o novo acesso"
            detail="O AlertaM atual foi preservado. Tente validar o novo acesso novamente."
          >
            <button
              type="button"
              onClick={() => void evaluateCandidate(candidate)}
            >
              Tentar novamente
            </button>
          </PairingScreen>
        </div>
      );
    }

    return (
      <PairingScreen
        title="Não foi possível confirmar o acesso"
        detail="A conexão falhou antes da confirmação. Tente novamente."
      >
        <button
          type="button"
          onClick={() => void evaluateCandidate(candidate)}
        >
          Tentar novamente
        </button>
      </PairingScreen>
    );
  }

  if (mode === "validating") {
    return (
      <PairingScreen
        title="Validando acesso"
        detail="Conferindo o pareamento com o AlertaM."
      />
    );
  }

  if (active) {
    return (
      <>
        {children(
          active,
          resetPairing,
          sessionReady,
          handleAccessRevoked,
          sessionInfo,
          (next) => void evaluateCandidate(next),
        )}
      </>
    );
  }

  return (
    <PairingScreen
      title="Alerta de Movimentações Marítimas"
      detail={
        mode === "invalid"
          ? "O acesso informado não é válido. Use um novo QR Code ou código de conexão."
          : "Conecte este aparelho ao AlertaM Desktop."
      }
    >
      <PairingConnectPanel
        onCandidate={(next) => void evaluateCandidate(next)}
      />
    </PairingScreen>
  );
}

function PairingScreen({
  title,
  detail,
  children,
}: {
  title: string;
  detail: string;
  children?: ReactNode;
}) {
  return (
    <main className="pairing-screen">
      <div className="pairing-screen__mark" aria-hidden="true">⚓</div>
      <h1>{title}</h1>
      <p>{detail}</p>
      {children}
    </main>
  );
}
