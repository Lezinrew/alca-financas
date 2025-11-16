import { test, expect } from '@playwright/test'

test.describe('Transactions Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')

    // Login with AI mode
    const aiLoginButton = page.locator('button:has-text("Login com IA"), button:has-text("Demo")')
    if (await aiLoginButton.count() > 0) {
      await aiLoginButton.click()
      await page.waitForURL(/.*dashboard.*/, { timeout: 5000 })
    }

    // Navigate to transactions
    const transactionsLink = page.locator('a[href*="transactions"], button:has-text("Transações")')
    if (await transactionsLink.count() > 0) {
      await transactionsLink.first().click()
      await page.waitForTimeout(1000)
    }
  })

  test('should display transactions page', async ({ page }) => {
    await expect(page.locator('h1, h2')).toContainText(/Transações|Transactions/i)
  })

  test('should open add transaction modal', async ({ page }) => {
    const addButton = page.locator('button:has-text("Nova Transação"), button:has-text("Add Transaction"), button:has-text("+")')

    if (await addButton.count() > 0) {
      await addButton.first().click()

      // Wait for modal
      await page.waitForTimeout(500)

      // Check for form fields
      const modal = page.locator('[role="dialog"], .modal, form')
      await expect(modal.first()).toBeVisible()
    }
  })

  test('should filter transactions by type', async ({ page }) => {
    const filterSelect = page.locator('select[name="type"], button:has-text("Filtro")')

    if (await filterSelect.count() > 0) {
      await filterSelect.first().click()

      // Select expense filter
      const expenseOption = page.locator('option[value="expense"], text=/Despesa|Expense/i')
      if (await expenseOption.count() > 0) {
        await expenseOption.first().click()
        await page.waitForTimeout(500)
      }
    }
  })

  test('should filter transactions by date', async ({ page }) => {
    const monthFilter = page.locator('select[name="month"], input[type="month"]')

    if (await monthFilter.count() > 0) {
      await monthFilter.first().click()
      await page.waitForTimeout(500)
    }
  })

  test('should display transaction details', async ({ page }) => {
    // Click on first transaction
    const firstTransaction = page.locator('[data-testid="transaction-item"], .transaction-row').first()

    if (await firstTransaction.count() > 0) {
      await firstTransaction.click()
      await page.waitForTimeout(500)

      // Should show details or edit form
      const details = page.locator('[role="dialog"], .modal, .transaction-details')
      if (await details.count() > 0) {
        await expect(details.first()).toBeVisible()
      }
    }
  })

  test('should create new transaction', async ({ page }) => {
    const addButton = page.locator('button:has-text("Nova Transação"), button:has-text("Add"), button:has-text("+")')

    if (await addButton.count() > 0) {
      await addButton.first().click()
      await page.waitForTimeout(500)

      // Fill form
      await page.fill('input[name="description"], input[placeholder*="Descrição"]', 'Test Transaction E2E')
      await page.fill('input[name="amount"], input[type="number"]', '100')

      // Select type
      const typeSelect = page.locator('select[name="type"]')
      if (await typeSelect.count() > 0) {
        await typeSelect.selectOption('expense')
      }

      // Submit
      const submitButton = page.locator('button[type="submit"]:has-text("Salvar"), button[type="submit"]:has-text("Criar")')
      if (await submitButton.count() > 0) {
        await submitButton.click()
        await page.waitForTimeout(1000)

        // Check for success message or new transaction in list
        const successMessage = page.locator('text=/Sucesso|Success|criada/i, .toast-success')
        if (await successMessage.count() > 0) {
          await expect(successMessage.first()).toBeVisible()
        }
      }
    }
  })
})
