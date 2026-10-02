import {
  useEffect,
  useRef,
  useState,
} from "react";
import type { IScannerControls } from "@zxing/browser";

import {
  parsePairingFragment,
  type Pairing,
} from "./pairing";
import {
  PairingCodeRedeemError,
  redeemPairingCode,
} from "./pairingCodeClient";


type PairingConnectPanelProps = {
  onCandidate: (pairing: Pairing) => void;
};

type ConnectMode = "choices" | "code" | "qr";

function pairingFromQrText(value: string): Pairing | null {
  let hash = value.trim();
  if (!hash.startsWith("#/pair/")) {
    try {
      hash = new URL(hash, window.location.origin).hash;
    } catch {
      return null;
    }
  }
  const parsed = parsePairingFragment(hash);
  if (!parsed) return null;
  return {
    deviceId: parsed.deviceId,
    viewSecret: parsed.viewSecret,
    pairingTicket: null,
    pairedAt: new Date().toISOString(),
  };
}

function displayCode(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 6);
  if (digits.length <= 3) return digits;
  return `${digits.slice(0, 3)} ${digits.slice(3)}`;
}

export function PairingConnectPanel({
  onCandidate,
}: PairingConnectPanelProps) {
  const [mode, setMode] = useState<ConnectMode>("choices");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const candidateRef = useRef(onCandidate);
  candidateRef.current = onCandidate;

  useEffect(() => {
    if (mode !== "qr") return;

    let active = true;
    const start = async () => {
      try {
        const { BrowserQRCodeReader } = await import("@zxing/browser");
        if (!active) return;
        const reader = new BrowserQRCodeReader();
        const controls = await reader.decodeFromConstraints(
          {
            audio: false,
            video: {
              facingMode: { ideal: "environment" },
            },
          },
          videoRef.current ?? undefined,
          (result, _scanError, currentControls) => {
            if (!active || !result) return;
            const candidate = pairingFromQrText(result.getText());
            if (!candidate) {
              setError("Este QR Code não pertence ao AlertaM.");
              return;
            }
            currentControls.stop();
            candidateRef.current(candidate);
          },
        );
        if (!active) {
          controls.stop();
          return;
        }
        controlsRef.current = controls;
      } catch {
        if (active) {
          setError(
            "Não foi possível abrir a câmera. Use o código de conexão como alternativa.",
          );
        }
      }
    };

    setError(null);
    void start();
    return () => {
      active = false;
      controlsRef.current?.stop();
      controlsRef.current = null;
    };
  }, [mode]);

  const submitCode = async () => {
    const normalized = code.replace(/\D/g, "");
    if (normalized.length !== 6 || busy) {
      setError("Digite os 6 dígitos do código de conexão.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const candidate = await redeemPairingCode(normalized);
      candidateRef.current(candidate);
    } catch (nextError) {
      setError(
        nextError instanceof PairingCodeRedeemError
          ? nextError.message
          : "Não foi possível validar o código agora.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (mode === "qr") {
    return (
      <div className="pairing-connect">
        <div className="pairing-connect__camera">
          <video
            ref={videoRef}
            muted
            playsInline
            aria-label="Leitor de QR Code"
          />
          <span>Posicione o QR Code do AlertaM dentro da câmera.</span>
        </div>
        {error ? <p className="pairing-connect__error" role="alert">{error}</p> : null}
        <button
          type="button"
          className="pairing-connect__secondary"
          onClick={() => setMode("choices")}
        >
          Voltar
        </button>
      </div>
    );
  }

  if (mode === "code") {
    return (
      <div className="pairing-connect">
        <label className="pairing-connect__code">
          <span>Código de conexão</span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            placeholder="000 000"
            maxLength={7}
            onChange={(event) => {
              setCode(displayCode(event.currentTarget.value));
              setError(null);
            }}
          />
        </label>
        <p className="pairing-connect__hint">
          Digite o código de 6 dígitos mostrado no AlertaM Desktop.
        </p>
        {error ? <p className="pairing-connect__error" role="alert">{error}</p> : null}
        <button
          type="button"
          className="pairing-connect__primary"
          disabled={busy}
          onClick={() => void submitCode()}
        >
          {busy ? "Validando..." : "Conectar"}
        </button>
        <button
          type="button"
          className="pairing-connect__secondary"
          disabled={busy}
          onClick={() => setMode("choices")}
        >
          Voltar
        </button>
      </div>
    );
  }

  return (
    <div className="pairing-connect">
      <button
        type="button"
        className="pairing-connect__primary"
        onClick={() => setMode("qr")}
      >
        <span className="pairing-connect__button-icon" aria-hidden="true">▣</span>
        Ler QR Code
      </button>
      <button
        type="button"
        className="pairing-connect__secondary"
        onClick={() => setMode("code")}
      >
        <span className="pairing-connect__button-icon" aria-hidden="true">123</span>
        Usar código de conexão
      </button>
    </div>
  );
}
