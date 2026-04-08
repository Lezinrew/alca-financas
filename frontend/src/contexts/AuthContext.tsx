import { createContext, useState, useContext, useEffect, useCallback, ReactNode } from 'react';
import { supabase } from '../utils/supabaseClient';
import { clearAuthStorage } from '../utils/tokenStorage';
import { authAPI } from '../utils/api';

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
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: { email: string; password: string }, rememberMe?: boolean) => Promise<{ success: boolean; message?: string }>;
  loginWithAI: () => Promise<{ success: boolean; message?: string }>;
  register: (userData: { name: string; email: string; password: string }) => Promise<{ success: boolean; message?: string }>;
  logout: () => void;
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

  const ensureBackendBootstrap = useCallback(async () => {
    // Bootstrap precisa rodar também quando a sessão é restaurada (F5/reopen),
    // não apenas no login manual.
    try {
      await authAPI.bootstrap();
    } catch {
      // Não bloqueia a sessão por falha transitória no bootstrap.
    }
  }, []);

  // Sessão do Supabase é a fonte de verdade (banco limpo / Supabase-only).
  useEffect(() => {
    const checkAuth = async () => {
      const { data, error } = await supabase.auth.getSession();
      if (error) {
        clearAuthStorage();
        setUser(null);
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      const sessionUser = data.session?.user ?? null;
      if (!sessionUser) {
        // Se não há sessão Supabase, limpa qualquer storage legado.
        clearAuthStorage();
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
    };

    checkAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      const sessionUser = session?.user ?? null;
      if (!sessionUser) {
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
        return { success: false, message: error?.message || 'Erro no login' };
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
      const errorMessage = error?.message || 'Erro no login';
      return {
        success: false,
        message: typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage)
      };
    }
  };

  const register = async (userData: { name: string; email: string; password: string }) => {
    try {
      const { data, error } = await supabase.auth.signUp({
        email: userData.email,
        password: userData.password,
        options: {
          data: {
            name: userData.name,
          },
        },
      });
      if (error) {
        return { success: false, message: error.message };
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
      const errorMessage = error?.message || 'Erro no cadastro';
      return {
        success: false,
        message: typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage)
      };
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
      const { error } = await supabase.auth.signUp({
        email: 'demo@alca.fin',
        password: 'demo123',
        options: { data: { name: 'Demo User' } },
      });
      if (error) {
        return { success: false, message: error.message };
      }
      // Tenta login após signup
      const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
        email: 'demo@alca.fin',
        password: 'demo123',
      });
      if (loginError) return { success: false, message: loginError.message };
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
      return { success: false, message: e?.message || 'Erro no login com IA' };
    }
  };

  const logout = () => {
    clearAuthStorage();
    Promise.resolve(supabase.auth.signOut()).catch(() => undefined);
    setUser(null);
    setIsAuthenticated(false);
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
