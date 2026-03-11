import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/__tests__/setup.tsx"],
    globals: true,
    exclude: ["tests/**", "node_modules/**"],
    server: {
      deps: {
        inline: [/react-markdown/, /remark-gfm/, /micromark/, /mdast/, /unified/, /remark/, /unist/, /devlop/, /ccount/, /escape-string-regexp/, /markdown-table/],
      },
    },
  },
});
