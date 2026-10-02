export type Pairing = {
  deviceId: string;
  viewSecret: string | null;
  pairingTicket?: string | null;
  pairedAt: string;
};

const PAIRING_PREFIX = "#/pair/";
const VIEW_SECRET_PATTERN = /^[A-Za-z0-9_-]{43,}$/;

export function isValidViewSecret(value: unknown): value is string {
  return typeof value === "string" && VIEW_SECRET_PATTERN.test(value);
}

export function parsePairingFragment(
  hash: string,
): { deviceId: string; viewSecret: string } | null {
  if (!hash.startsWith(PAIRING_PREFIX)) {
    return null;
  }

  const payload = hash.slice(PAIRING_PREFIX.length);
  const separator = payload.indexOf("?");
  if (separator <= 0) {
    return null;
  }

  const encodedDevice = payload.slice(0, separator);
  const query = payload.slice(separator + 1);

  try {
    const deviceId = decodeURIComponent(encodedDevice);
    if (!deviceId.trim()) {
      return null;
    }

    const viewSecret = new URLSearchParams(query).get("token");
    if (!isValidViewSecret(viewSecret)) {
      return null;
    }

    return { deviceId, viewSecret };
  } catch {
    return null;
  }
}

export function clearPairingFragment(history: History): void {
  history.replaceState(
    history.state,
    "",
    `${window.location.pathname}${window.location.search}`,
  );
}
