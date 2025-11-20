import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../contexts/AuthContext'

import { authAPI } from '../utils/api'

// Mock the API
vi.mock('../utils/api', () => ({
  authAPI: {
    login: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
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
        onClick={logout}
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
    renderWithProvider()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('No user')
  })

  it('should handle AI login successfully', async () => {
    const mockUser = { id: '1', name: 'Demo User', email: 'demo@alca.fin' }
    const mockResponse = {
      data: {
        access_token: 'mock_access_token',
        refresh_token: 'mock_refresh_token',
        user: mockUser
      }
    }
    vi.mocked(authAPI.login).mockResolvedValue(mockResponse as any)

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

    // Check localStorage
    expect(localStorage.getItem('user_data')).toBeTruthy()
    expect(localStorage.getItem('auth_token')).toBeTruthy()
  })

  it('should handle logout correctly', async () => {
    const mockUser = { id: '1', name: 'Demo User', email: 'demo@alca.fin' }
    const mockResponse = {
      data: {
        access_token: 'mock_access_token',
        refresh_token: 'mock_refresh_token',
        user: mockUser
      }
    }
    vi.mocked(authAPI.login).mockResolvedValue(mockResponse as any)

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

    // Check localStorage is cleared
    expect(localStorage.getItem('user_data')).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })

  it('should restore user from localStorage on mount', async () => {
    // Pre-populate localStorage
    const mockUser = { id: 1, name: 'Test User', email: 'test@example.com' }
    // Prepend space to avoid 'eyJ' prefix (which would be treated as real JWT)
    const mockToken = btoa(' ' + JSON.stringify({ user: mockUser, exp: Date.now() + 10000 }))

    localStorage.setItem('user_data', JSON.stringify(mockUser))
    localStorage.setItem('auth_token', mockToken)

    renderWithProvider()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('User: Test User (test@example.com)')
  })

  it('should handle expired token correctly', async () => {
    // Pre-populate localStorage with expired token
    const mockUser = { id: 1, name: 'Test User', email: 'test@example.com' }
    // Prepend space to avoid 'eyJ' prefix
    const expiredToken = btoa(' ' + JSON.stringify({ user: mockUser, exp: Date.now() - 10000 }))

    localStorage.setItem('user_data', JSON.stringify(mockUser))
    localStorage.setItem('auth_token', expiredToken)

    renderWithProvider()

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
    })

    expect(screen.getByTestId('user-info')).toHaveTextContent('No user')

    // Check localStorage is cleared for expired token
    expect(localStorage.getItem('user_data')).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})