/**
 * URL usada em links de confirmação de cadastro enviados pelo Supabase Auth.
 * Tem de constar em Supabase → Authentication → URL Configuration → Redirect URLs.
 */
export function getAuthEmailRedirectTo(): string | undefined {
  const explicit = (import.meta.env.VITE_AUTH_EMAIL_REDIRECT_TO as string | undefined)?.trim();
  if (explicit) return explicit;
  if (typeof window === 'undefined') return undefined;
  return `${window.location.origin}/login`;
}
