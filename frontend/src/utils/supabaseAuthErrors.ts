type AuthErrLike = {
  message?: string;
  code?: string;
  status?: number;
} | null | undefined;

/**
 * Converte mensagens técnicas do Supabase Auth em texto útil em PT-BR.
 * Rate limit de e-mail é quota do projeto Supabase, não falha do frontend.
 */
export function formatSupabaseAuthError(err: AuthErrLike): string {
  const raw = (err?.message ?? '').trim();
  const code = (typeof err?.code === 'string' ? err.code : '').toLowerCase();
  const blob = `${raw} ${code}`.toLowerCase();

  if (
    blob.includes('rate limit') ||
    blob.includes('over_email_send_rate_limit') ||
    blob.includes('email rate limit') ||
    blob.includes('too many requests')
  ) {
    return (
      'Limite de envio de e-mails atingido no Supabase (proteção anti-abuso). ' +
      'Aguarde cerca de uma hora ou use outro e-mail. Para desenvolvimento: no painel Supabase, ' +
      'Authentication → Providers → Email, desative "Confirm email" ou configure SMTP próprio.'
    );
  }

  if (
    blob.includes('already registered') ||
    blob.includes('user already exists') ||
    code === 'user_already_exists'
  ) {
    return 'Já existe uma conta com este e-mail. Entre com a senha ou use "Esqueci a senha".';
  }

  if (blob.includes('invalid login credentials') || code === 'invalid_credentials') {
    return 'E-mail ou senha incorretos.';
  }

  if (blob.includes('password') && blob.includes('least')) {
    return 'A senha não cumpre os requisitos mínimos do provedor.';
  }

  return raw || 'Não foi possível concluir a operação. Tente novamente.';
}
