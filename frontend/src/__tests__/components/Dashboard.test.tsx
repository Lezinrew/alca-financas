import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { AuthProvider } from '@/contexts/AuthContext'

// ...

it('should render dashboard title', () => {
  render(
    <AuthProvider>
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    </AuthProvider>
  )

  expect(screen.getByText(/Dashboard/i)).toBeInTheDocument()
})

it('should display KPI cards', async () => {
  render(
    <AuthProvider>
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    </AuthProvider>
  )

  await waitFor(() => {
    expect(screen.getByText(/Saldo Atual/i)).toBeInTheDocument()
    expect(screen.getByText(/Receitas/i)).toBeInTheDocument()
    expect(screen.getByText(/Despesas/i)).toBeInTheDocument()
  })
})

it('should show loading state initially', () => {
  render(
    <AuthProvider>
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    </AuthProvider>
  )

  expect(screen.getByText(/Carregando/i)).toBeInTheDocument()
})
})
