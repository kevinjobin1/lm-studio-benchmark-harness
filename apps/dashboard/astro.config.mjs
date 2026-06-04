import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import cloudflare from "@astrojs/cloudflare";

export default defineConfig({
  integrations: [react()],
  output: "server",
  adapter: cloudflare({
    mode: "pages",
    assets: {
      name: "STATIC_CONTENT",
    },
  }),
  site: "https://modellens-dashboard.kevin-jobin-1.workers.dev",
  base: "/",
  build: {
    assets: "assets",
  },
  vite: {
    define: {
      "import.meta.env.PUBLIC_SSE_WORKER_URL": JSON.stringify(
        process.env.PUBLIC_SSE_WORKER_URL ||
          "https://modellens-sse-bridge.kevin-jobin-1.workers.dev"
      ),
    },
  },
});
