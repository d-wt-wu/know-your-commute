import { test, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { join } from 'node:path'

// Opt-in, read-only checks of the attributed source bundle loaded into Neon.
// These never seed, truncate, migrate or modify the production database.
test('real Neon records flow through API, filters, pages and source health', async ({
  page,
  request,
}, info) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const query = 'route=102&start=2025-01-01&end=2025-01-31'
  const summaryResponse = await request.get(`/api/v1/summary?${query}`)
  expect(summaryResponse.ok()).toBe(true)
  const summary = await summaryResponse.json()
  expect(summary.summary.reported_records).toBe(65)
  expect(summary.summary.median_recorded_delay_minutes).toBe(20)
  const snapshot = summary.context.snapshot.id
  const patterns = await (
    await request.get(`/api/v1/patterns?${query}&snapshot_id=${snapshot}`)
  ).json()
  expect(patterns.context.snapshot.id).toBe(snapshot)
  expect(
    patterns.daily_records.reduce(
      (sum: number, row: { reported_records: number }) => sum + row.reported_records,
      0,
    ),
  ).toBe(65)
  await page.goto(`/?${query}`)
  await expect(page.locator('.metric-value').first()).toHaveText('65')
  await expect(page.locator('.metric-value').nth(1)).toHaveText('20 min')
  await expect(page.locator('.metric-value').nth(2)).toHaveText('65')
  await expect(page.locator('.records-panel')).toHaveAttribute('aria-busy', 'false')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  if (process.env.COMMUTE_NEON_SCREENSHOT_DIR) {
    await mkdir(process.env.COMMUTE_NEON_SCREENSHOT_DIR, { recursive: true })
    await page.screenshot({
      path: join(process.env.COMMUTE_NEON_SCREENSHOT_DIR, `ttc-neon-${info.project.name}.jpg`),
      type: 'jpeg',
      quality: 85,
      fullPage: true,
    })
  }
  await page.getByRole('button', { name: 'Next page', exact: true }).click()
  await expect(page.getByText('Page 2 of 3', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('Page 2 of 3', { exact: true })).toBeVisible()
  await page.getByLabel('To', { exact: true }).fill('2025-01-15')
  await page.getByRole('button', { name: 'Explore records', exact: true }).click()
  await expect(page.locator('.metric-value').first()).toHaveText('39')
  await page.goBack()
  await expect(page.locator('.metric-value').first()).toHaveText('65')
  await page.getByRole('link', { name: 'Data health', exact: true }).click()
  await expect(page.getByText('107,349 / 0', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Keep the explorer on your iPhone', exact: true }),
  ).toBeVisible()
  expect(errors).toEqual([])
})
