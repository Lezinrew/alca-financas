/* @refresh reset */
// Provider + useAuth no mesmo ficheiro: sem isto o Vite avisa "useAuth export is incompatible" no HMR.
import { createContext, useState, useContext, useEffect, useCallback, ReactNode, useRef } from 'react';
import { supabase } from '../utils/supabaseClient';
import { clearAuthStorage } from '../utils/tokenStorage';
import { authAPI, invalidateLookupCache } from '../utils/api';
import { formatSupabaseAuthError } from '../utils/supabaseAuthErrors';
import { getAuthEmailRedirectTo } from '../utils/authRedirect';

/** Logs de diagnóstico de auth (`true` só em `vite dev`). Para forçar em build: `VITE_AUTH_DIAG_LOGS=1`. */
const AUTH_DIAG_LOGS =
  (typeof import.meta !== 'undefined' && import.meta.env?.DEV) ||
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_AUTH_DIAG_LOGS === '1');

function authDiag(...args: unknown[]) {
  if (AUTH_DIAG_LOGS) {
    // eslint-disable-next-line no-console
    console.log('[auth:diag]', ...args);
  }
}

interface AuthProviderInfo {
  provider: string;
  email_verified?: boolean;
}

interface User {
  id: string;
  name: string;
  email: string;
  auth_providers?: AuthProviderInfo[];
  is_admin?: boolean;
  role?: string;
  status?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: { email: string; password: string }, rememberMe?: boolean) => Promise<{ success: boolean; message?: string }>;
  loginWithAI: () => Promise<{ success: boolean; message?: string }>;
  register: (userData: { name: string; email: string; password: string }) => Promise<{ success: boolean; message?: string }>;
  logout: () => Promise<void>;
  updateUser: (userData: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth deve ser usado dentro de AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const bootstrapInFlightRef = useRef<Promise<void> | null>(null);
  const bootstrapDoneForUserRef = useRef<string | null>(null);
  /** Evita rajadas de GET /api/auth/me (HMR, onAuthStateChange, vários efeitos). */
  const lastProfileSyncAtRef = useRef(0);

  const resetLocalAuthCaches = () => {
    bootstrapDoneForUserRef.current = null;
    bootstrapInFlightRef.current = null;
    lastProfileSyncAtRef.current = 0;
    clearAuthStorage();
    invalidateLookupCache();
  };

  const syncProfileFromBackend = useCallback(async (force = false) => {
    const now = Date.now();
    if (!force && now - lastProfileSyncAtRef.current < 12_000) {
      return;
    }
    lastProfileSyncAtRef.current = now;
    try {
      const { data } = await authAPI.getMe();
      if (!data?.id) return;
      setUser((prev) => ({
        id: data.id,
        name: data.name ?? prev?.name ?? 'Usuário',
        email: data.email ?? prev?.email ?? '',
        auth_providers: prev?.auth_providers,
        role: data.role,
        status: data.status,
        is_admin: Boolean(data.is_admin ?? data.role === 'admin'),
      }));
    } catch {
      /* perfil opcional */
    }
  }, []);

  const ensureBackendBootstrap = useCallback(async () => {
    // Bootstrap precisa rodar também quando a sessão é restaurada (F5/reopen),
    // não apenas no login manual.
    try {
      const { data } = await supabase.auth.getSession();
      const userId = data.session?.user?.id ?? null;
      if (!userId) {
        authDiag('bootstrap:skip (sem sessão)');
        return;
      }
      if (bootstrapDoneForUserRef.current === userId) {
        await syncProfileFromBackend(false);
        return;
      }
      authDiag('bootstrap:start', { userIdPrefix: `${userId.slice(0, 8)}…` });
      if (!bootstrapInFlightRef.current) {
        bootstrapInFlightRef.current = authAPI
          .bootstrap()
          .then(() => {
            bootstrapDoneForUserRef.current = userId;
            authDiag('bootstrap:ok');
          })
          .finally(() => {
            bootstrapInFlightRef.current = null;
          });
      }
      try {
        await bootstrapInFlightRef.current;
      } catch {
        authDiag('bootstrap:erro (ignorado para não bloquear sessão)');
      }
      await syncProfileFromBackend(true);
    } catch {
      authDiag('bootstrap:erro (ignorado para não bloquear sessão)');
      await syncProfileFromBackend(true);
    }
  }, [syncProfileFromBackend]);

  // Sessão do Supabase é a fonte de verdade (banco limpo / Supabase-only).
  useEffect(() => {
    const checkAuth = async () => {
      authDiag('checkAuth:início');
      const { data, error } = await supabase.auth.getSession();
      authDiag('checkAuth:getSession', { error: error?.message ?? null, hasSession: !!data.session });
      if (error) {
        resetLocalAuthCaches();
        setUser(null);
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      const sessionUser = data.session?.user ?? null;
      if (!sessionUser) {
        // Se não há sessão Supabase, limpa qualquer storage legado e caches.
        resetLocalAuthCaches();
        setUser(null);
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      setUser({
        id: sessionUser.id,
        email: sessionUser.email ?? '',
        name:
          (sessionUser.user_metadata?.name as string | undefined) ??
          (sessionUser.email ? sessionUser.email.split('@')[0] : 'Usuário'),
      });
      setIsAuthenticated(true);
      await ensureBackendBootstrap();
      setLoading(false);
      authDiag('checkAuth:fim', { autenticado: true });
    };

    checkAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      const sessionUser = session?.user ?? null;
      authDiag('onAuthStateChange', { event, hasSession: !!sessionUser });
      if (!sessionUser) {
        resetLocalAuthCaches();
        setUser(null);
        setIsAuthenticated(false);
        return;
      }
      setUser({
        id: sessionUser.id,
        email: sessionUser.email ?? '',
        name:
          (sessionUser.user_metadata?.name as string | undefined) ??
          (sessionUser.email ? sessionUser.email.split('@')[0] : 'Usuário'),
      });
      setIsAuthenticated(true);
      void ensureBackendBootstrap();
    });

    return () => subscription.unsubscribe();
  }, [ensureBackendBootstrap]);

  // Após promover admin via SQL ou outro separador, voltar ao app deve atualizar role/is_admin.
  useEffect(() => {
    if (!isAuthenticated) return;
    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      void syncProfileFromBackend(true);
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [isAuthenticated, syncProfileFromBackend]);

  const login = async (credentials: { email: string; password: string }, rememberMe = false) => {
    try {
      // Após apagar/recriar usuário no Supabase, tokens antigos no browser invalidam refresh e derrubam a sessão.
      clearAuthStorage();
      await supabase.auth.signOut({ scope: 'local' }).catch(() => {});

      const { data, error } = await supabase.auth.signInWithPassword({
        email: credentials.email,
        password: credentials.password,
      });
      if (error || !data.session?.user) {
        return {
          success: false,
          message: error ? formatSupabaseAuthError(error) : 'E-mail ou senha incorretos.',
        };
      }

      const sessionUser = data.session.user;
      setUser({
        id: sessionUser.id,
        email: sessionUser.email ?? '',
        name:
          (sessionUser.user_metadata?.name as string | undefined) ??
          (sessionUser.email ? sessionUser.email.split('@')[0] : 'Usuário'),
      });
      setIsAuthenticated(true);

      // Inicializa tenant/categorias/registro custom no backend (idempotente)
      await ensureBackendBootstrap();

      // Supabase persiste a sessão; "rememberMe" é controlado via storage customizado.
      // Aqui, mantemos compatibilidade mínima com o comportamento anterior limpando
      // qualquer storage legado e deixando o Supabase cuidar da sessão.
      if (!rememberMe) {
        // Se o usuário não quer persistir entre reinícios, o ideal seria configurar
        // storage do Supabase para sessionStorage. Mantemos simples por enquanto:
        // Supabase persistirá e o usuário poderá fazer logout.
      }

      return { success: true };
    } catch (error: any) {
      return { success: false, message: formatSupabaseAuthError(error) };
    }
  };

  const register = async (userData: { name: string; email: string; password: string }) => {
    try {
      // Evita sessão antiga + novo cadastro no mesmo browser (estado híbrido).
      clearAuthStorage();
      await supabase.auth.signOut({ scope: 'local' }).catch(() => undefined);

      const emailRedirectTo = getAuthEmailRedirectTo();
      const { data, error } = await supabase.auth.signUp({
        email: userData.email,
        password: userData.password,
        options: {
          ...(emailRedirectTo ? { emailRedirectTo } : {}),
          data: {
            name: userData.name,
          },
        },
      });
      if (error) {
        return { success: false, message: formatSupabaseAuthError(error) };
      }

      // Se confirmação de e-mail estiver habilitada, talvez não haja sessão.
      if (data.session?.user) {
        const sessionUser = data.session.user;
        setUser({
          id: sessionUser.id,
          email: sessionUser.email ?? userData.email,
          name: userData.name,
        });
        setIsAuthenticated(true);
        await ensureBackendBootstrap();
        return { success: true };
      }

      return { success: true, message: 'Conta criada. Verifique seu e-mail para confirmar o cadastro.' };
    } catch (error: any) {
      return { success: false, message: formatSupabaseAuthError(error) };
    }
  };

  const loginWithAI = async () => {
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: 'demo@alca.fin',
        password: 'demo123',
      });
      if (!error && data.session?.user) {
        const sessionUser = data.session.user;
        setUser({
          id: sessionUser.id,
          email: sessionUser.email ?? 'demo@alca.fin',
          name:
            (sessionUser.user_metadata?.name as string | undefined) ??
            (sessionUser.email ? sessionUser.email.split('@')[0] : 'Demo User'),
        });
        setIsAuthenticated(true);
        await ensureBackendBootstrap();
        return { success: true };
      }
    } catch {
      // ignore
    }

    try {
      const demoRedirect = getAuthEmailRedirectTo();
      const { error } = await supabase.auth.signUp({
        email: 'demo@alca.fin',
        password: 'demo123',
        options: {
          ...(demoRedirect ? { emailRedirectTo: demoRedirect } : {}),
          data: { name: 'Demo User' },
        },
      });
      if (error) {
        return { success: false, message: formatSupabaseAuthError(error) };
      }
      // Tenta login após signup
      const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
        email: 'demo@alca.fin',
        password: 'demo123',
      });
      if (loginError) return { success: false, message: formatSupabaseAuthError(loginError) };
      if (loginData.session?.user) {
        const sessionUser = loginData.session.user;
        setUser({
          id: sessionUser.id,
          email: sessionUser.email ?? 'demo@alca.fin',
          name:
            (sessionUser.user_metadata?.name as string | undefined) ??
            (sessionUser.email ? sessionUser.email.split('@')[0] : 'Demo User'),
        });
        setIsAuthenticated(true);
        await ensureBackendBootstrap();
      }
      return { success: true };
    } catch (e: any) {
      return { success: false, message: formatSupabaseAuthError(e) };
    }
  };

  const logout = async (): Promise<void> => {
    authDiag('logout:clique / início');
    bootstrapDoneForUserRef.current = null;
    bootstrapInFlightRef.current = null;

    try {
      authDiag('logout:signOut:before');
      const { error: globalErr } = await supabase.auth.signOut({ scope: 'global' });
      if (globalErr) {
        authDiag('logout:signOut:global falhou, tentando local', globalErr.message);
        await supabase.auth.signOut({ scope: 'local' });
      }
      authDiag('logout:signOut:after');
    } catch (e) {
      authDiag('logout:signOut:exceção', e);
      await supabase.auth.signOut({ scope: 'local' }).catch(() => undefined);
    }

    clearAuthStorage();
    invalidateLookupCache();
    setUser(null);
    setIsAuthenticated(false);

    const { data: after } = await supabase.auth.getSession();
    authDiag('logout:estado sessão após limpeza', { hasSession: !!after.session });
    authDiag('logout:fim');
  };

  const updateUser = (userData: User) => {
    setUser(userData);
  };

  const value = {
    user,
    loading,
    isAuthenticated,
    login,
    loginWithAI,
    register,
    logout,
    updateUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
