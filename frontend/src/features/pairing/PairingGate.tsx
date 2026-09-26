import {
  type ReactNode,
  useCallback,
  useEffect,
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

type PairingFetcher = typeof getSnapshot;
type GateMode = "idle" | "validating" | "temporary" | "invalid";

type PairingGateProps = {
  fetcher?: PairingFetcher;
  children: (pairing: Pairing, reset: () => void) => ReactNode;
};
export function PairingGate({
  fetcher = getSnapshot,
  children,
}: PairingGateProps) {
  const [active, setActive] = useState<Pairing | null>(() => loadPairing());
  const [candidate, setCandidate] = useState<Pairing | null>(null);
  const [mode, setMode] = useState<GateMode>("idle");

  const reset = useCallback(() => {
    clearPairing();
    setActive(null);
    setCandidate(null);
    setMode("idle");
  }, []);

  const promote = useCallback((next: Pairing) => {
    savePairing(next);
    setActive(next);
    setCandidate(null);
    setMode("idle");
  }, []);

  const validate = useCallback(
    async (next: Pairing) => {
      setMode("validating");
      try {
        await fetcher(next);
        promote(next);
      } catch (error) {
        if (
          error instanceof SnapshotUnavailableError ||
          error instanceof UnsupportedSnapshotError
        ) {
          promote(next);
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
    [fetcher, promote],
  );

  useEffect(() => {
    const hash = window.location.hash;
    if (!hash.startsWith("#/pair/")) return;

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
  }, [validate]);
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
    return <>{children(active, reset)}</>;
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
