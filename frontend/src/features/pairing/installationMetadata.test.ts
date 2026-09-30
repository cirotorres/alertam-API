import {
  INSTALLATION_METADATA_STORAGE_KEY,
  clearInstallationMetadata,
  loadInstallationMetadata,
  storeInstallationMetadata,
} from "./installationMetadata";

beforeEach(() => {
  localStorage.clear();
});

test("persists and restores installation metadata", () => {
  const metadata = {
    installationId: "11111111-2222-4333-8444-555555555555",
    displayCode: "K7M4Q2",
    platform: "ios" as const,
  };

  storeInstallationMetadata(metadata);

  expect(loadInstallationMetadata()).toEqual(metadata);
});

test.each([
  "{",
  JSON.stringify({ installationId: "not-a-uuid", displayCode: "K7M4Q2", platform: "ios" }),
  JSON.stringify({ installationId: "11111111-2222-4333-8444-555555555555", displayCode: "O0I1AA", platform: "ios" }),
  JSON.stringify({ installationId: "11111111-2222-4333-8444-555555555555", displayCode: "K7M4Q2", platform: "windows" }),
])("invalid metadata is discarded", (raw) => {
  localStorage.setItem(INSTALLATION_METADATA_STORAGE_KEY, raw);

  expect(loadInstallationMetadata()).toBeNull();
  expect(localStorage.getItem(INSTALLATION_METADATA_STORAGE_KEY)).toBeNull();
});

test("clear removes stored metadata", () => {
  storeInstallationMetadata({
    installationId: "11111111-2222-4333-8444-555555555555",
    displayCode: "K7M4Q2",
    platform: "android",
  });

  clearInstallationMetadata();

  expect(loadInstallationMetadata()).toBeNull();
});
