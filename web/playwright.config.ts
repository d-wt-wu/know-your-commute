import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const database =
  process.env.BROWSER_TEST_DATABASE_URL ??
  'postgresql+psycopg://commute:commute_local@127.0.0.1:54329/commute_browser_test'

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['junit', { outputFile: 'test-results/browser.xml' }]],
  use: { baseURL: 'http://127.0.0.1:8002', trace: 'retain-on-failure' },
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
    command: '.venv/bin/python scripts/run_local.py --port 8002',
    cwd: root,
    url: 'http://127.0.0.1:8002/api/v1/ready',
    reuseExistingServer: false,
    env: { DATABASE_URL: database },
  },
})
