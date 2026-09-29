export const INSTALLATION_ID_STORAGE_KEY =
  "alertam.mobile.installation.v1";


export function loadInstallationId(): string | null {
  const value = localStorage.getItem(INSTALLATION_ID_STORAGE_KEY);
  if (value === null || value.trim().length === 0) {
    return null;
  }
  return value;
}


export function getOrCreateInstallationId(
  randomUUID: () => string = () => crypto.randomUUID(),
): string {
  const existing = loadInstallationId();
  if (existing !== null) {
    return existing;
  }

  const created = randomUUID();
  localStorage.setItem(INSTALLATION_ID_STORAGE_KEY, created);
  return created;
}


export function storeInstallationId(installationId: string): void {
  localStorage.setItem(INSTALLATION_ID_STORAGE_KEY, installationId);
}

export function clearInstallationId(): void {
  localStorage.removeItem(INSTALLATION_ID_STORAGE_KEY);
}
