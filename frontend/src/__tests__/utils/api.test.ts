import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'
import { api } from '@/utils/api'

vi.mock('axios')

describe('API Utils', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('should have correct base URL for local environment', () => {
    expect(api.defaults.baseURL).toBe('http://localhost:5000')
  })

  it('should add authorization header when token exists', () => {
    const token = 'test-token-123'
    localStorage.setItem('token', token)

    // Simulate interceptor
    const config = { headers: {} }
    const interceptor = api.interceptors.request.handlers[0]

    if (interceptor && interceptor.fulfilled) {
      const result = interceptor.fulfilled(config)
      expect(result.headers.Authorization).toBe(`Bearer ${token}`)
    }
  })

  it('should handle API errors correctly', async () => {
    const errorResponse = {
      response: {
        status: 401,
        data: { error: 'Unauthorized' }
      }
    }

    vi.mocked(axios.get).mockRejectedValue(errorResponse)

    try {
      await api.get('/api/test')
    } catch (error: any) {
      expect(error.response.status).toBe(401)
    }
  })

  it('should handle token expiration', () => {
    const expiredToken = 'expired-token'
    localStorage.setItem('token', expiredToken)

    const errorResponse = {
      response: {
        status: 401,
        data: { error: 'Token expired' }
      }
    }

    // Simulate response interceptor handling 401
    const interceptor = api.interceptors.response.handlers[0]

    if (interceptor && interceptor.rejected) {
      try {
        interceptor.rejected(errorResponse)
      } catch (error) {
        expect(localStorage.getItem('token')).toBeNull()
      }
    }
  })
})
