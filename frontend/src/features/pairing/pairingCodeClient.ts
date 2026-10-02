import type { Pairing } from "./pairing";

export type PairingCodeErrorKind =
  | "invalid"
  | "rate-limited"
  | "temporary";

export class PairingCodeRedeemError extends Error {
  readonly kind: PairingCodeErrorKind;

  constructor(kind: PairingCodeErrorKind) {
    const message =
      kind === "invalid"
        ? "Código inválido ou expirado."
        : kind === "rate-limited"
          ? "Muitas tentativas. Aguarde um minuto e tente novamente."
          : "Não foi possível validar o código agora.";
    super(message);
    this.name = "PairingCodeRedeemError";
    this.kind = kind;
  }
}

type PairingTicketResponse = {
  device_id: string;
  pairing_ticket: string;
  expires_at: string;
};

function isPairingTicketResponse(
  value: unknown,
): value is PairingTicketResponse {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.device_id === "string" &&
    candidate.device_id.trim().length > 0 &&
    typeof candidate.pairing_ticket === "string" &&
    candidate.pairing_ticket.length >= 32 &&
    typeof candidate.expires_at === "string"
  );
}

export async function redeemPairingCode(
  code: string,
): Promise<Pairing> {
  let response: Response;
  try {
    response = await fetch("/api/v1/mobile/pairing/code", {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ code }),
    });
  } catch {
    throw new PairingCodeRedeemError("temporary");
  }

  if (response.status === 401) {
    throw new PairingCodeRedeemError("invalid");
  }
  if (response.status === 429) {
    throw new PairingCodeRedeemError("rate-limited");
  }
  if (!response.ok) {
    throw new PairingCodeRedeemError("temporary");
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new PairingCodeRedeemError("temporary");
  }
  if (!isPairingTicketResponse(body)) {
    throw new PairingCodeRedeemError("temporary");
  }

  return {
    deviceId: body.device_id,
    viewSecret: null,
    pairingTicket: body.pairing_ticket,
    pairedAt: new Date().toISOString(),
  };
}
