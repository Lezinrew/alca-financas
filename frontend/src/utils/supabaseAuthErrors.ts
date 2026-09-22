type AuthErrLike = {
  message?: string;
  code?: string;
  status?: number;
  name?: string;
} | null | undefined;

export const AUTH_ERROR_NETWORK =
  'Não foi possível conectar. Verifique sua internet e tente novamente.';
export const AUTH_ERROR_RATE_LIMIT =
  'Muitas tentativas. Aguarde alguns minutos e tente novamente.';
export const AUTH_ERROR_SIGNUP_NEUTRAL =
  'Não foi possível concluir o cadastro com este e-mail. Se você já tem conta, entre ou recupere a senha.';
export const AUTH_ERROR_FALLBACK =
  'Não foi possível concluir a operação. Tente novamente.';

/**
 * Converte erros do Supabase Auth em texto útil em PT-BR, sem vazar detalhes
 * técnicos (provedor, SMTP, painéis) nem a existência de um e-mail cadastrado.
 * `fallback` permite uma mensagem padrão específica do contexto (ex.: reset de senha).
 */
export function formatSupabaseAuthError(err: AuthErrLike, fallback: string = AUTH_ERROR_FALLBACK): string {
  const raw = (err?.message ?? '').trim();
  const code = (typeof err?.code === 'string' ? err.code : '').toLowerCase();
  const name = (typeof err?.name === 'string' ? err.name : '').toLowerCase();
  const status = typeof err?.status === 'number' ? err.status : undefined;
  const blob = `${raw} ${code} ${name}`.toLowerCase();

  const isFetchTypeError = name === 'typeerror' && blob.includes('fetch');
  if (
    isFetchTypeError ||
    name === 'authretryablefetcherror' ||
    blob.includes('failed to fetch') ||
    blob.includes('network error') ||
    blob.includes('networkerror') ||
    blob.includes('load failed') ||
    blob.includes('retryable') ||
    status === 0 ||
    status === 502 ||
    status === 503 ||
    status === 504
  ) {
    return AUTH_ERROR_NETWORK;
  }

  if (
    status === 429 ||
    blob.includes('rate limit') ||
    blob.includes('rate_limit') ||
    blob.includes('too many requests')
  ) {
    return AUTH_ERROR_RATE_LIMIT;
  }

  if (
    blob.includes('already registered') ||
    blob.includes('user already exists') ||
    code === 'user_already_exists' ||
    code === 'email_exists'
  ) {
    return AUTH_ERROR_SIGNUP_NEUTRAL;
  }

  if (blob.includes('invalid login credentials') || code === 'invalid_credentials') {
    return 'E-mail ou senha incorretos.';
  }

  if (code === 'email_not_confirmed' || blob.includes('email not confirmed')) {
    return 'Confirme seu e-mail antes de entrar. Verifique sua caixa de entrada e o spam.';
  }

  if (code === 'weak_password' || (blob.includes('password') && blob.includes('least'))) {
    return 'A senha não cumpre os requisitos mínimos. Use pelo menos 6 caracteres.';
  }

  if (code === 'same_password') {
    return 'A nova senha deve ser diferente da senha atual.';
  }

  if (
    code === 'otp_expired' ||
    code === 'flow_state_expired' ||
    code === 'flow_state_not_found' ||
    blob.includes('expired') ||
    blob.includes('invalid or has expired')
  ) {
    return 'Link inválido ou expirado. Solicite um novo link.';
  }

  return fallback;
}
