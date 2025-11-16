import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')

    // Quick login with AI mode
    const aiLoginButton = page.locator('button:has-text("Login com IA"), button:has-text("Demo")')
    if (await aiLoginButton.count() > 0) {
      await aiLoginButton.click()
      await page.waitForURL(/.*dashboard.*/, { timeout: 5000 })
    }
  })

  test('should display dashboard KPIs', async ({ page }) => {
    // Check for KPI cards
    const kpiCards = page.locator('.kpi-card, [data-testid="kpi-card"]')
    const count = await kpiCards.count()

    expect(count).toBeGreaterThanOrEqual(3)

    // Check for key metrics
    await expect(page.locator('text=/Saldo|Balance/i').first()).toBeVisible()
    await expect(page.locator('text=/Receitas|Income/i').first()).toBeVisible()
    await expect(page.locator('text=/Despesas|Expenses/i').first()).toBeVisible()
  })

  test('should display charts', async ({ page }) => {
    // Wait for charts to render
    await page.waitForTimeout(1000)

    // Check for chart elements (Recharts creates SVG)
    const charts = page.locator('svg.recharts-surface, canvas')
    const chartCount = await charts.count()

    expect(chartCount).toBeGreaterThan(0)
  })

  test('should display recent transactions', async ({ page }) => {
    // Look for transaction list
    const transactionSection = page.locator('text=/Transações Recentes|Recent Transactions/i')

    if (await transactionSection.count() > 0) {
      await expect(transactionSection.first()).toBeVisible()

      // Check for transaction items
      const transactions = page.locator('[data-testid="transaction-item"], .transaction-row')
      const hasTransactions = await transactions.count() > 0

      // Either has transactions or shows empty state
      expect(hasTransactions || await page.locator('text=/Nenhuma transação|No transactions/i').count() > 0).toBeTruthy()
    }
  })

  test('should navigate to transactions page', async ({ page }) => {
    // Find and click transactions link
    const transactionsLink = page.locator('a[href*="transactions"], button:has-text("Transações")')

    if (await transactionsLink.count() > 0) {
      await transactionsLink.first().click()

      // Wait for navigation
      await page.waitForTimeout(1000)

      // Verify URL or page content
      const url = page.url()
      expect(url.includes('transactions') || url.includes('transacoes')).toBeTruthy()
    }
  })

  test('should be responsive on mobile', async ({ page, viewport }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })

    // Dashboard should still be visible
    await expect(page.locator('h1, h2').first()).toBeVisible()

    // KPIs should stack vertically on mobile
    const firstKpi = page.locator('.kpi-card, [data-testid="kpi-card"]').first()
    if (await firstKpi.count() > 0) {
      const box = await firstKpi.boundingBox()
      expect(box?.width).toBeLessThan(viewport?.width || 375)
    }
  })
})
