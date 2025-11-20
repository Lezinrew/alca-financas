import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import Dashboard from '@/components/dashboard/Dashboard'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'

// Mock the API module
vi.mock('@/utils/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  },
  dashboardAPI: {
    getAdvanced: vi.fn()
  },
  authAPI: {
    getMe: vi.fn().mockResolvedValue({ data: { id: '1', name: 'Test User' } }),
    login: vi.fn(),
    register: vi.fn()
  },
  formatCurrency: (val: number) => `R$ ${val}`
}))

// Import mocked functions to define return values
import { dashboardAPI } from '@/utils/api'

describe('Dashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('auth_token', 'test-token')

    // Mock dashboard data
    const mockDashboardResponse = {
      data: {
        summary: {
          total_income: 3000,
          total_expense: 2000
        },
        monthly_evolution: [],
        expense_by_category: [],
        recent_transactions: []
      },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {}
    }
    vi.mocked(dashboardAPI.getAdvanced).mockResolvedValue(mockDashboardResponse as any)

    // Mock fetch for accounts
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ([
        { id: '1', name: 'Bank', current_balance: 5000, is_active: true, type: 'checking' }
      ])
    } as Response)
  })

  it('should show loading state initially', () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </AuthProvider>
    )

    // Check for skeleton elements (animate-pulse class)
    const skeletons = document.getElementsByClassName('animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('should render dashboard content after loading', async () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </AuthProvider>
    )

    // Wait for loading to finish and content to appear
    await waitFor(() => {
      expect(screen.getByText(/Saldo Atual/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/Receitas/i)).toBeInTheDocument()
    expect(screen.getByText(/Despesas/i)).toBeInTheDocument()
  })

  it('should display correct values from API', async () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </AuthProvider>
    )

    await waitFor(() => {
      // 5000 balance
      expect(screen.getByText(/R\$ 5000/)).toBeInTheDocument()
      // 3000 income
      expect(screen.getByText(/R\$ 3000/)).toBeInTheDocument()
      // 2000 expense
      expect(screen.getByText(/R\$ 2000/)).toBeInTheDocument()
    })
  })
})
