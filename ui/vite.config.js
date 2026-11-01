import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built files land inside the Python package and are served by `promptdock serve --ui`
// at /ui/. During development, `npm run dev` proxies API calls to a local server.
export default defineConfig({
  plugins: [react()],
  base: "/ui/",
  build: {
    outDir: "../src/promptdock/ui/static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 800, // one bundle for an internal dashboard is fine
  },
  server: {
    proxy: {
      "^/(prompts|evals|health)": "http://127.0.0.1:8000",
    },
  },
});
