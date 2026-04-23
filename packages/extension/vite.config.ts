import { copyFileSync } from "node:fs";
import { resolve } from "node:path";

// import.meta.dirname requires Node ≥21.2; safe given vite 7 peer requirement
const __dirname = import.meta.dirname;

import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(__dirname, "src/background/index.ts"),
        espn: resolve(__dirname, "src/content/espn.ts"),
        yahoo: resolve(__dirname, "src/content/yahoo.ts"),
      },
      output: {
        format: "es",
        entryFileNames: "[name].js",
      },
    },
  },
  plugins: [
    {
      name: "copy-extension-manifest",
      closeBundle() {
        copyFileSync(resolve(__dirname, "manifest.json"), resolve(__dirname, "dist/manifest.json"));
      },
    },
  ],
});
