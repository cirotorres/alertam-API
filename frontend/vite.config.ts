import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

import {
  PWA_INJECT_MANIFEST_CONFIG,
} from "./src/features/install/pwaConfig";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");

  return {
    server: {
      proxy: {
        "/api": {
          target: env.VITE_DEV_API_TARGET || "http://localhost:8000",
          changeOrigin: false,
        },
      },
    },
    plugins: [
    react(),
    VitePWA({
      ...PWA_INJECT_MANIFEST_CONFIG,
      includeAssets: ["icons/apple-touch-icon.png"],
      manifest: {
        name: "Alerta de Movimentações Marítimas",
        short_name: "AlertaM",
        description: "Consulta mobile somente leitura do AlertaM",
        lang: "pt-BR",
        theme_color: "#123f5b",
        background_color: "#f4f7f9",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icons/pwa-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/pwa-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/pwa-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,png,ico,svg}"],
      },
    }),
  ],
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
