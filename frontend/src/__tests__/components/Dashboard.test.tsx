import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Dashboard } from '@/components/dashboard/Dashboard'
import { BrowserRouter } from 'react-router-dom'

vi.mock('@/utils/api', () => ({
  api: {
    get: vi.fn(() => Promise.resolve({
      data: {
        balance: 5000,
        income: 3000,
        expenses: 2000,
        openTickets: 5
      }
    }))
  }
}))

describe('Dashboard Component', () => {
  it('should render dashboard title', () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(screen.getByText(/Dashboard/i)).toBeInTheDocument()
  })

  it('should display KPI cards', async () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText(/Saldo Atual/i)).toBeInTheDocument()
      expect(screen.getByText(/Receitas/i)).toBeInTheDocument()
      expect(screen.getByText(/Despesas/i)).toBeInTheDocument()
    })
  })

  it('should show loading state initially', () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(screen.getByText(/Carregando/i)).toBeInTheDocument()
  })
})
