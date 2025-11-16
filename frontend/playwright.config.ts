import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E Test Configuration
 * Supports both local and production environments
 */
const isProduction = process.env.TEST_ENV === 'production'
const baseURL = isProduction
  ? 'https://alcahub.com.br'
  : 'http://localhost:3000'

export default defineConfig({
  testDir: './e2e',

  // Test timeout
  timeout: 30 * 1000,

  // Global setup/teardown
  fullyParallel: true,

  // Fail on CI if tests are marked as flaky
  forbidOnly: !!process.env.CI,

  // Retry on CI
  retries: process.env.CI ? 2 : 0,

  // Workers
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['list']
  ],

  use: {
    // Base URL
    baseURL,

    // Collect trace on failure
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'retain-on-failure',

    // Ignore HTTPS errors in local
    ignoreHTTPSErrors: !isProduction,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    // Mobile tests
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],

  // Web server for local testing
  webServer: !isProduction ? {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  } : undefined,
})
