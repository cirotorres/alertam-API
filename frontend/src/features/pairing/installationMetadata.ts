import type { DevicePlatform } from "./devicePlatform";

export const INSTALLATION_METADATA_STORAGE_KEY =
  "alertam.mobile.installation.metadata.v1";

export type InstallationMetadata = {
  installationId: string;
  displayCode: string;
  platform: DevicePlatform;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DISPLAY_CODE_PATTERN = /^[A-HJ-NP-Z2-9]{6}$/;

function isInstallationMetadata(value: unknown): value is InstallationMetadata {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.installationId === "string" &&
    UUID_PATTERN.test(candidate.installationId) &&
    typeof candidate.displayCode === "string" &&
    DISPLAY_CODE_PATTERN.test(candidate.displayCode) &&
    (candidate.platform === "ios" ||
      candidate.platform === "android" ||
      candidate.platform === "other")
  );
}

export function loadInstallationMetadata(): InstallationMetadata | null {
  const raw = localStorage.getItem(INSTALLATION_METADATA_STORAGE_KEY);
  if (raw === null) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (isInstallationMetadata(parsed)) {
      return parsed;
    }
  } catch {
    // Invalid persisted state is discarded below.
  }

  localStorage.removeItem(INSTALLATION_METADATA_STORAGE_KEY);
  return null;
}

export function storeInstallationMetadata(
  metadata: InstallationMetadata,
): void {
  if (!isInstallationMetadata(metadata)) {
    throw new TypeError("Invalid installation metadata.");
  }
  localStorage.setItem(
    INSTALLATION_METADATA_STORAGE_KEY,
    JSON.stringify(metadata),
  );
}

export function clearInstallationMetadata(): void {
  localStorage.removeItem(INSTALLATION_METADATA_STORAGE_KEY);
}
