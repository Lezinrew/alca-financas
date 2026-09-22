import { describe, expect, it } from 'vitest';
import {
  AUTH_ERROR_FALLBACK,
  AUTH_ERROR_NETWORK,
  AUTH_ERROR_RATE_LIMIT,
  AUTH_ERROR_SIGNUP_NEUTRAL,
  formatSupabaseAuthError,
} from '../../utils/supabaseAuthErrors';

describe('formatSupabaseAuthError', () => {
  it('mapeia falhas de rede/fetch para mensagem de conexão', () => {
    expect(formatSupabaseAuthError(new TypeError('Failed to fetch'))).toBe(AUTH_ERROR_NETWORK);
    expect(formatSupabaseAuthError({ name: 'AuthRetryableFetchError', message: 'x', status: 0 })).toBe(AUTH_ERROR_NETWORK);
    expect(formatSupabaseAuthError({ message: 'Network Error' })).toBe(AUTH_ERROR_NETWORK);
    expect(formatSupabaseAuthError({ message: 'Bad gateway', status: 502 })).toBe(AUTH_ERROR_NETWORK);
  });

  it('mapeia rate limit sem citar provedor', () => {
    const msg = formatSupabaseAuthError({ message: 'email rate limit exceeded', code: 'over_email_send_rate_limit' });
    expect(msg).toBe(AUTH_ERROR_RATE_LIMIT);
    expect(formatSupabaseAuthError({ message: 'Too Many Requests', status: 429 })).toBe(AUTH_ERROR_RATE_LIMIT);
    expect(msg).not.toMatch(/supabase|smtp|painel/i);
  });

  it('usa fallback fixo em português em vez da mensagem crua', () => {
    expect(formatSupabaseAuthError({ message: 'Some raw provider error' })).toBe(AUTH_ERROR_FALLBACK);
    expect(formatSupabaseAuthError(null)).toBe(AUTH_ERROR_FALLBACK);
    expect(formatSupabaseAuthError({ message: 'raw' }, 'Contexto próprio.')).toBe('Contexto próprio.');
  });

  it('não vaza existência de e-mail no cadastro', () => {
    const msg = formatSupabaseAuthError({ message: 'User already registered', code: 'user_already_exists' });
    expect(msg).toBe(AUTH_ERROR_SIGNUP_NEUTRAL);
    expect(msg).not.toMatch(/já existe/i);
  });
});
