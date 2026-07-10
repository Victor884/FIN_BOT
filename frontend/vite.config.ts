import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// Plain Vite + React SPA. TanStack Start scaffolding was removed in favor of
// React Router DOM per project requirements.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
    tsconfigPaths: true,
  },
  server: {
    host: "::",
    port: 8080,
    strictPort: true,
  },
});
