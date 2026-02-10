/**
 * Centraliza leitura/escrita de tokens e user_data conforme "Lembrar-me":
 * - rememberMe = true  → localStorage (persiste ao fechar o navegador)
 * - rememberMe = false → sessionStorage (limpa ao fechar a aba)
 * Permite que a API e o AuthContext usem a mesma fonte sem reescrever o contexto inteiro.
 */

const AUTH_TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_DATA_KEY = 'user_data';
const REMEMBER_ME_KEY = 'auth_remember_me';

function getStorage(rememberMe: boolean): Storage {
  return rememberMe ? localStorage : sessionStorage;
}

/** Persiste tokens e user no storage escolhido; opcionalmente grava preferência de rememberMe no localStorage. */
export function setAuthTokens(
  accessToken: string,
  refreshToken: string | null,
  userData: string,
  rememberMe: boolean
): void {
  const storage = getStorage(rememberMe);
  storage.setItem(AUTH_TOKEN_KEY, accessToken);
  if (refreshToken) storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  storage.setItem(USER_DATA_KEY, userData);
  localStorage.setItem(REMEMBER_ME_KEY, rememberMe ? '1' : '0');
}

/** Retorna o token de acesso: primeiro sessionStorage, depois localStorage (compatível com fluxo atual). */
export function getAuthToken(): string | null {
  return sessionStorage.getItem(AUTH_TOKEN_KEY) ?? localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_TOKEN_KEY) ?? localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getUserData(): string | null {
  return sessionStorage.getItem(USER_DATA_KEY) ?? localStorage.getItem(USER_DATA_KEY);
}

/** Limpa todos os dados de auth em ambos os storages (logout ou sessão expirada). */
export function clearAuthStorage(): void {
  [localStorage, sessionStorage].forEach((s) => {
    s.removeItem(AUTH_TOKEN_KEY);
    s.removeItem(REFRESH_TOKEN_KEY);
    s.removeItem(USER_DATA_KEY);
  });
  localStorage.removeItem(REMEMBER_ME_KEY);
}

export function getRememberMe(): boolean {
  return localStorage.getItem(REMEMBER_ME_KEY) === '1';
}
