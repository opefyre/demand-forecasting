import { defineConfig } from "vite";
export default defineConfig({
  base: "/ui/",
  build: { outDir: "../app/static/client", emptyOutDir: true },
});
