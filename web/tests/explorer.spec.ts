import { test, expect } from '@playwright/test'

// These expectations describe scripts/seed_browser.py's labelled synthetic data.
// Real-source counts are verified separately in Python and the local browser QA.
test('route/date filters, pagination, history and data health', async ({ page }) => {
  await page.goto('/?route=102&start=2025-01-01&end=2025-01-31')
  await expect(page.locator('.metric-value').first()).toHaveText('35')
  await expect(page.locator('.metric-value').nth(1)).toHaveText('20 min')
  await expect(page.locator('.metric-value').nth(2)).toHaveText('34')
  await expect(page.getByText('Page 1 of 2', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Next page', exact: true }).click()
  await expect(page.getByText('Page 2 of 2', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('Page 2 of 2', { exact: true })).toBeVisible()
  await page.getByLabel('To', { exact: true }).fill('2025-01-01')
  await page.getByRole('button', { name: 'Explore records', exact: true }).click()
  await expect(page.locator('.metric-value').first()).toHaveText('20')
  await page.goBack()
  await expect(page.locator('.metric-value').first()).toHaveText('35')
  await page.getByLabel('Bus route', { exact: true }).fill('116')
  await page.getByLabel('Bus route', { exact: true }).press('Enter')
  await expect(page.locator('.metric-value').first()).toHaveText('5')
  await page.getByRole('link', { name: 'Data health', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Data health', exact: true })).toBeVisible()
  await expect(page.getByText('40 / 0', { exact: true })).toBeVisible()
  await expect(page.getByText('Latest attempt', { exact: true }).first()).toBeVisible()
})

test('empty, partial coverage, loading and retry states', async ({ page }) => {
  let release: () => void = () => {}
  const responseGate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/api/v1/summary*', async (route) => {
    await responseGate
    await route.continue()
  })
  await page.goto('/?route=102&start=2025-01-01&end=2025-01-31')
  await expect(page.getByText('Loading historical records…', { exact: true })).toBeVisible()
  release()
  await expect(page.locator('.metric-value').first()).toHaveText('35')
  await page.unroute('**/api/v1/summary*')
  await page.getByLabel('Bus route', { exact: true }).fill('99999')
  await page.getByLabel('Bus route', { exact: true }).press('Enter')
  await expect(
    page.getByRole('heading', { name: 'No matching records in the loaded data.', exact: true }),
  ).toBeVisible()
  await page.goto('/?route=102&start=2024-01-01&end=2025-01-31')
  await expect(page.getByText(/Your range extends beyond/)).toBeVisible()
  await page.route('**/api/v1/summary*', (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          code: 'database_unavailable',
          message: 'Historical data is temporarily unavailable.',
        },
      },
    }),
  )
  await page.getByRole('button', { name: 'Check for a newer imported source', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.unroute('**/api/v1/summary*')
  const recovered = page.waitForResponse(
    (response) => response.url().includes('/api/v1/summary') && response.status() === 200,
  )
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await recovered
  await expect(page.locator('.records-panel')).toHaveAttribute('aria-busy', 'false')
  await expect(page.locator('.metric-value').first()).toHaveText('35')
})

test('mobile page fits and tables have their own scrolling area', async ({ page }) => {
  await page.goto('/?route=102&start=2025-01-01&end=2025-01-31')
  await expect(page.locator('.metric-value').first()).toHaveText('35')
  const layout = await page.evaluate(() => ({
    pageFits: document.documentElement.scrollWidth <= innerWidth,
    tableContained:
      document.querySelector('.table-scroll')!.clientWidth <= document.documentElement.clientWidth,
  }))
  expect(layout.pageFits).toBe(true)
  expect(layout.tableContained).toBe(true)
  await page.getByRole('link', { name: 'About', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'A record is not a trip.', exact: true }),
  ).toBeVisible()
})

test('Home Screen assets load and installation guidance is available', async ({
  page,
  request,
}) => {
  await page.goto('/about')
  await expect(
    page.getByRole('heading', { name: 'Keep the explorer on your iPhone', exact: true }),
  ).toBeVisible()
  await expect(page.getByText(/An internet connection is required/)).toBeVisible()
  const manifestUrl = await page.locator('link[rel="manifest"]').getAttribute('href')
  const response = await request.get(manifestUrl!)
  expect(response.ok()).toBe(true)
  expect(response.headers()['content-type']).toContain('application/manifest+json')
  const manifest = await response.json()
  for (const icon of manifest.icons) {
    const png = await request.get(icon.src)
    expect(png.headers()['content-type']).toContain('image/png')
    expect((await png.body()).subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
  }
})
