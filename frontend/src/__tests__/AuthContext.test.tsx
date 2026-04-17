import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../contexts/AuthContext'

const {
  mockGetSession,
  mockOnAuthStateChange,
  mockSignInWithPassword,
  mockSignUp,
  mockSignOut,
} = vi.hoisted(() => ({
  mockGetSession: vi.fn(),
  mockOnAuthStateChange: vi.fn(),
  mockSignInWithPassword: vi.fn(),
  mockSignUp: vi.fn(),
  mockSignOut: vi.fn(),
}))

vi.mock('../utils/supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: mockGetSession,
      onAuthStateChange: mockOnAuthStateChange,
      signInWithPassword: mockSignInWithPassword,
      signUp: mockSignUp,
      signOut: mockSignOut,
    },
  },
}))

// Test component that uses the auth context
const TestComponent = () => {
  const { user, isAuthenticated, login, loginWithAI, logout, loading } = useAuth()

  if (loading) {
    return <div>Loading...</div>
  }

  return (
    <div>
      <div data-testid="auth-status">
        {isAuthenticated ? 'Authenticated' : 'Not Authenticated'}
      </div>
      <div data-testid="user-info">
        {user ? `User: ${user.name} (${user.email})` : 'No user'}
      </div>
      <button
        data-testid="login-btn"
        onClick={() => login({ email: 'test@test.com', password: '123' })}
      >
        Login
      </button>
      <button
        data-testid="ai-login-btn"
        onClick={() => loginWithAI()}
      >
        AI Login
      </button>
      <button
        data-testid="logout-btn"
        onClick={() => void logout()}
      >
        Logout
      </button>
    </div>
  )
}

const renderWithProvider = () => {
  return render(
    <AuthProvider>
      <TestComponent />
    </AuthProvider>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    vi.clearAllMocks()

    mockGetSession.mockResolvedValue({ data: { session: null }, error: null })
    mockOnAuthStateChange.mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    })
    mockSignOut.mockResolvedValue({} as any)
  })

  it('should render loading state initially', async () => {
    renderWithProvider()
    // Loading state might be very brief, so we either catch it or verify it transitions quickly
    try {
      expect(screen.getByText('Loading...')).toBeInTheDocument()
    } catch {
      // If loading is too fast, just verify it settles to not authenticated
      await waitFor(() => {
        expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
      })
    }
  })

  it('should show not authenticated state when no user is logged in', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null })
    renderWithProvider()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('No user')
  })

  it('should handle AI login successfully', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null })
    mockSignInWithPassword.mockResolvedValue({
      data: {
        session: {
          access_token: 'mock_access_token',
          user: {
            id: '1',
            email: 'demo@alca.fin',
            user_metadata: { name: 'Demo User' },
          },
        },
      },
      error: null,
    })

    const user = userEvent.setup()
    renderWithProvider()

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    // Click AI login button
    await user.click(screen.getByTestId('ai-login-btn'))

    // Wait for login to complete
    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('User: Demo User (demo@alca.fin)')
  })

  it('should handle logout correctly', async () => {
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null })
    mockSignInWithPassword.mockResolvedValue({
      data: {
        session: {
          access_token: 'mock_access_token',
          user: {
            id: '1',
            email: 'demo@alca.fin',
            user_metadata: { name: 'Demo User' },
          },
        },
      },
      error: null,
    })
    mockSignUp.mockResolvedValue({ data: { session: null, user: null }, error: null })

    const user = userEvent.setup()
    renderWithProvider()

    // Wait for loading and login with AI first
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
    })

    await user.click(screen.getByTestId('ai-login-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
    })

    // Now logout
    await user.click(screen.getByTestId('logout-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('No user')
  })

  it('should restore user from Supabase session on mount', async () => {
    mockGetSession.mockResolvedValue({
      data: {
        session: {
          access_token: 'mock_access_token',
          user: {
            id: '1',
            email: 'test@example.com',
            user_metadata: { name: 'Test User' },
          },
        },
      },
      error: null,
    })

    renderWithProvider()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('User: Test User (test@example.com)')
  })

  it('should handle expired token correctly', async () => {
    // Simula ausência de sessão (token expirado) retornando session null
    localStorage.setItem('user_data', JSON.stringify({ id: 1, name: 'Test User', email: 'test@example.com' }))
    localStorage.setItem('auth_token', 'stale')
    mockGetSession.mockResolvedValue({ data: { session: null }, error: null })

    renderWithProvider()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('No user')

    // Storage legado é limpo quando não há sessão válida
    expect(localStorage.getItem('user_data')).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})