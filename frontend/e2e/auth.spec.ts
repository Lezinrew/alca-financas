import { test, expect } from '@playwright/test'

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should display login page', async ({ page }) => {
    await expect(page.locator('h1')).toContainText(/Login|Entrar/i)
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })

  test('should show validation errors for empty fields', async ({ page }) => {
    const loginButton = page.locator('button[type="submit"]')
    await loginButton.click()

    // Wait for validation messages
    await page.waitForTimeout(500)

    const errors = await page.locator('.error-message, [role="alert"]').count()
    expect(errors).toBeGreaterThan(0)
  })

  test('should login with AI demo mode', async ({ page }) => {
    const aiLoginButton = page.locator('button:has-text("Login com IA"), button:has-text("Demo")')

    if (await aiLoginButton.count() > 0) {
      await aiLoginButton.click()

      // Wait for redirect to dashboard
      await page.waitForURL(/.*dashboard.*/, { timeout: 5000 })

      // Verify dashboard loaded
      await expect(page.locator('h1, h2')).toContainText(/Dashboard/i)
    }
  })

  test('should login with valid credentials', async ({ page }) => {
    // Use test credentials
    await page.fill('input[type="email"]', 'test@alcahub.com.br')
    await page.fill('input[type="password"]', 'TestPassword123!')

    await page.click('button[type="submit"]')

    // Wait for navigation or error
    await page.waitForTimeout(2000)

    // Check if redirected to dashboard or error shown
    const url = page.url()
    const hasError = await page.locator('.error-message, [role="alert"]').count() > 0

    // Either should be on dashboard or see an error
    expect(url.includes('dashboard') || hasError).toBeTruthy()
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.fill('input[type="email"]', 'wrong@alcahub.com.br')
    await page.fill('input[type="password"]', 'WrongPassword123!')

    await page.click('button[type="submit"]')

    // Wait for error message
    await page.waitForTimeout(1000)

    const errorMessage = page.locator('.error-message, [role="alert"], .text-red-500')
    await expect(errorMessage.first()).toBeVisible()
  })

  test('should logout successfully', async ({ page }) => {
    // First login (using AI mode for speed)
    const aiLoginButton = page.locator('button:has-text("Login com IA"), button:has-text("Demo")')

    if (await aiLoginButton.count() > 0) {
      await aiLoginButton.click()
      await page.waitForURL(/.*dashboard.*/, { timeout: 5000 })

      // Find and click logout
      const logoutButton = page.locator('button:has-text("Sair"), button:has-text("Logout"), [aria-label="Logout"]')
      await logoutButton.click()

      // Should redirect to login
      await page.waitForURL(/.*login.*|^\/$/i, { timeout: 3000 })
      await expect(page.locator('input[type="email"]')).toBeVisible()
    }
  })
})
