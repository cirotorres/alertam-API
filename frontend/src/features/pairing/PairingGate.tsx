import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  AccessRevokedError,
  SnapshotUnavailableError,
  TemporaryApiError,
  UnsupportedSnapshotError,
  getSnapshot,
} from "../../api/snapshotClient";
import {
  clearPairingFragment,
  parsePairingFragment,
  type Pairing,
} from "./pairing";
import {
  clearPairing,
  loadPairing,
  savePairing,
} from "./pairingStorage";
import {
  clearMobileSession,
  createMobileSession,
  recoverMobileSession,
} from "./mobileSessionClient";

type PairingFetcher = typeof getSnapshot;
type GateMode = "idle" | "validating" | "temporary" | "invalid";

type PairingGateProps = {
  fetcher?: PairingFetcher;
  sessionCreator?: (pairing: Pairing) => Promise<void>;
  sessionRecoverer?: () => Promise<Pairing | null>;
  sessionClearer?: () => Promise<void>;
  children: (
    pairing: Pairing,
    reset: () => void,
    sessionReady: boolean,
  ) => ReactNode;
};
export function PairingGate({
  fetcher = getSnapshot,
  sessionCreator = createMobileSession,
  sessionRecoverer = recoverMobileSession,
  sessionClearer = clearMobileSession,
  children,
}: PairingGateProps) {
  const [active, setActive] = useState<Pairing | null>(() => loadPairing());
  const [candidate, setCandidate] = useState<Pairing | null>(null);
  const [mode, setMode] = useState<GateMode>("idle");
  const [sessionReady, setSessionReady] = useState(false);
  const skipNextRecoveryRef = useRef(false);
  const syncedSessionRef = useRef<string | null>(null);

  const reset = useCallback(() => {
    skipNextRecoveryRef.current = true;
    syncedSessionRef.current = null;
    clearPairing();
    void sessionClearer();
    setSessionReady(false);
    setActive(null);
    setCandidate(null);
    setMode("idle");
  }, [sessionClearer]);

  const promote = useCallback((next: Pairing, ready = true) => {
    if (next.viewSecret) {
      savePairing(next);
    }
    setSessionReady(ready);
    setActive(next);
    setCandidate(null);
    setMode("idle");
  }, []);

  const validate = useCallback(
    async (next: Pairing) => {
      setMode("validating");
      try {
        await fetcher(next);
        await sessionCreator(next);
        syncedSessionRef.current = `${next.deviceId}:${next.viewSecret}`;
        promote(next);
      } catch (error) {
        if (
          error instanceof SnapshotUnavailableError ||
          error instanceof UnsupportedSnapshotError
        ) {
          try {
            await sessionCreator(next);
            syncedSessionRef.current = `${next.deviceId}:${next.viewSecret}`;
            promote(next);
          } catch (sessionError) {
            if (sessionError instanceof AccessRevokedError) {
              setCandidate(null);
              setMode("invalid");
              return;
            }
            setCandidate(next);
            setMode("temporary");
          }
          return;
        }
        if (error instanceof AccessRevokedError) {
          setCandidate(null);
          setMode("invalid");
          return;
        }
        if (error instanceof TemporaryApiError) {
          setCandidate(next);
          setMode("temporary");
          return;
        }
        setCandidate(next);
        setMode("temporary");
      }
    },
    [fetcher, promote, sessionCreator],
  );

  useEffect(() => {
    const hash = window.location.hash;
    if (!hash.startsWith("#/pair/")) {
      if (active?.viewSecret) {
        const sessionKey = `${active.deviceId}:${active.viewSecret}`;
        if (syncedSessionRef.current !== sessionKey) {
          setSessionReady(false);
          void sessionCreator(active)
            .then(() => {
              syncedSessionRef.current = sessionKey;
              setSessionReady(true);
            })
            .catch(() => {
              setSessionReady(false);
            });
        }
        return;
      }
      if (active) {
        return;
      }
      if (skipNextRecoveryRef.current) {
        skipNextRecoveryRef.current = false;
        return;
      }

      setMode("validating");
      void sessionRecoverer()
        .then((recovered) => {
          if (recovered) {
            promote(recovered);
          } else {
            setMode("idle");
          }
        })
        .catch(() => setMode("idle"));
      return;
    }

    const parsed = parsePairingFragment(hash);
    clearPairingFragment(window.history);
    if (!parsed) {
      setMode("invalid");
      return;
    }

    const next: Pairing = {
      deviceId: parsed.deviceId,
      viewSecret: parsed.viewSecret,
      pairedAt: new Date().toISOString(),
    };
    setCandidate(next);
    void validate(next);
  }, [active, promote, sessionCreator, sessionRecoverer, validate]);
  if (mode === "temporary" && candidate) {
    return (
      <PairingScreen
        title="Não foi possível confirmar o acesso"
        detail="A conexão falhou antes da confirmação. Tente novamente."
      >
        <button type="button" onClick={() => void validate(candidate)}>
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
    return <>{children(active, reset, sessionReady)}</>;
  }

  return (
    <PairingScreen
      title="Alerta de Movimentações Marítimas"
      detail={
        mode === "invalid"
          ? "O acesso informado não é válido. Gere um novo QR Code em Conectar Celular."
          : "Abra Conectar Celular no AlertaM Desktop e escaneie o QR Code."
      }
    />
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
