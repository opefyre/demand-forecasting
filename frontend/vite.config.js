import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
export default defineConfig({
  base: "/ui/",
  server: {
    fs: { allow: [fileURLToPath(new URL(".", import.meta.url)),
      fileURLToPath(new URL("../app/static/fonts", import.meta.url))] },
  },
  build: { outDir: "../app/static/client", emptyOutDir: true },
});
