export const API_RUNTIME_CACHING = {
  urlPattern: /\/api\/v1\//,
  handler: "NetworkOnly" as const,
  method: "GET" as const,
};
