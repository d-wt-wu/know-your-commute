import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  testDir: './neon-tests',
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: [['list'], ['junit', { outputFile: 'test-results/neon-browser.xml' }]],
  use: { baseURL: 'http://127.0.0.1:8004', trace: 'retain-on-failure' },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } },
    },
    {
      name: 'mobile',
      use: { ...devices['Desktop Chrome'], viewport: { width: 375, height: 812 } },
    },
  ],
  webServer: {
    command: 'npm start -- --port 8004',
    cwd: fileURLToPath(new URL('..', import.meta.url)),
    url: 'http://127.0.0.1:8004/api/v1/ready',
    timeout: 45_000,
    reuseExistingServer: false,
  },
})
