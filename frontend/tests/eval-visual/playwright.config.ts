import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1280, height: 900 },
  },
  webServer: {
    command: "npm run dev",
    port: 5173,
    cwd: "../..",
    reuseExistingServer: true,
  },
  outputDir: "../../test-results/eval-visual",
  snapshotPathTemplate:
    "{testDir}/__screenshots__/{testFilePath}/{arg}{ext}",
});
