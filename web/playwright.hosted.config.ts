import { defineConfig, devices } from '@playwright/test'

const address = process.env.COMMUTE_PUBLIC_BASE_URL
if (!address) throw new Error('Set COMMUTE_PUBLIC_BASE_URL to the deployed HTTPS website.')
const base = new URL(address)
if (
  base.protocol !== 'https:' ||
  base.username ||
  base.password ||
  base.pathname !== '/' ||
  base.search ||
  base.hash
) {
  throw new Error('COMMUTE_PUBLIC_BASE_URL must be an HTTPS origin without credentials or filters.')
}

// Reuse the real-source journeys without starting a local server or seeding data.
export default defineConfig({
  testDir: './neon-tests',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [['list'], ['junit', { outputFile: 'test-results/hosted-browser.xml' }]],
  use: {
    baseURL: base.origin,
    actionTimeout: 20_000,
    navigationTimeout: 90_000,
    trace: 'retain-on-failure',
  },
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
})
