import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: { baseURL: "http://127.0.0.1:4200", headless: true },
  webServer: {
    command:
      "node node_modules/@angular/cli/bin/ng.js serve --proxy-config proxy.conf.cjs --host 127.0.0.1",
    url: "http://127.0.0.1:4200",
    reuseExistingServer: !process.env["CI"],
    timeout: 120000,
  },
});
