export const PWA_INJECT_MANIFEST_CONFIG = {
  strategies: "injectManifest",
  srcDir: "src",
  filename: "sw.ts",
  registerType: "autoUpdate",
} as const;

export const API_RUNTIME_CACHING = {
  urlPattern: /\/api\/v1\//,
  handler: "NetworkOnly" as const,
  method: "GET" as const,
};
