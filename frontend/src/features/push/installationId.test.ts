import { beforeEach, expect, test, vi } from "vitest";

import {
  INSTALLATION_ID_STORAGE_KEY,
  clearInstallationId,
  createFreshInstallationId,
  getOrCreateInstallationId,
  loadInstallationId,
} from "./installationId";


beforeEach(() => {
  localStorage.clear();
});


test("installation_id_persists_across_reloads_until_explicit_clear", () => {
  const generated = "11111111-2222-4333-8444-555555555555";
  const randomUUID = vi.fn(() => generated);

  expect(getOrCreateInstallationId(randomUUID)).toBe(generated);
  expect(loadInstallationId()).toBe(generated);
  expect(localStorage.getItem(INSTALLATION_ID_STORAGE_KEY)).toBe(generated);

  const shouldNotRun = vi.fn(() => "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee");
  expect(getOrCreateInstallationId(shouldNotRun)).toBe(generated);
  expect(shouldNotRun).not.toHaveBeenCalled();

  clearInstallationId();
  expect(loadInstallationId()).toBeNull();
});


test("fresh installation id does not persist before promotion", () => {
  const generated = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
  const randomUUID = vi.fn(() => generated);

  expect(createFreshInstallationId(randomUUID)).toBe(generated);
  expect(loadInstallationId()).toBeNull();
  expect(localStorage.getItem(INSTALLATION_ID_STORAGE_KEY)).toBeNull();
});
