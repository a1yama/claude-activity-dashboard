import { defineConfig } from "@playwright/test";
import path from "path";

const PROJECT_ROOT = path.resolve(__dirname, "..");
const FIXTURE_DB = path.join(__dirname, "fixtures", "claude_activity.db");

const DATASETTE_PORT = 8766;
const VITE_PORT = 5174;

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  use: {
    baseURL: `http://localhost:${VITE_PORT}`,
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
  webServer: [
    {
      command: `${PROJECT_ROOT}/.venv/bin/datasette serve ${FIXTURE_DB} --metadata ${PROJECT_ROOT}/metadata.yml --plugins-dir ${PROJECT_ROOT}/plugins/ --port ${DATASETTE_PORT}`,
      port: DATASETTE_PORT,
      reuseExistingServer: false,
      timeout: 15_000,
    },
    {
      command: "npm run dev",
      cwd: path.join(PROJECT_ROOT, "frontend"),
      port: VITE_PORT,
      reuseExistingServer: false,
      timeout: 15_000,
      env: {
        DATASETTE_PORT: String(DATASETTE_PORT),
        VITE_PORT: String(VITE_PORT),
      },
    },
  ],
});
