import { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { authAPI } from '../utils/api';
import {
  setAuthTokens,
  getAuthToken,
  getUserData,
  clearAuthStorage,
} from '../utils/tokenStorage';

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

  // Verifica se usuário está logado (token/user em sessionStorage ou localStorage conforme Lembrar-me)
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken();
      const userData = getUserData();

      if (token && userData) {
        try {
          if (token.startsWith('eyJ')) {
            try {
              const response = await authAPI.getMe();
              setUser(response.data);
              setIsAuthenticated(true);
            } catch {
              throw new Error('Token inválido');
            }
          } else {
            try {
              const tokenData = JSON.parse(atob(token));
              if (tokenData.exp && tokenData.exp < Date.now()) {
                throw new Error('Token expired');
              }
              setUser(JSON.parse(userData));
              setIsAuthenticated(true);
            } catch {
              throw new Error('Token inválido');
            }
          }
        } catch {
          clearAuthStorage();
          setUser(null);
          setIsAuthenticated(false);
        }
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
      setLoading(false);
    };

    checkAuth();
  }, []);

  const login = async (credentials: { email: string; password: string }, rememberMe = false) => {
    try {
      const response = await authAPI.login(credentials);
      const { access_token, refresh_token, user: userData } = response.data;

      setAuthTokens(access_token, refresh_token || null, JSON.stringify(userData), rememberMe);
      setUser(userData);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error: any) {
      const errorMessage = error?.response?.data?.error || error?.message || 'Erro no login';
      return {
        success: false,
        message: typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage)
      };
    }
  };

  const register = async (userData: { name: string; email: string; password: string }, rememberMe = false) => {
    try {
      const response = await authAPI.register(userData);
      const { access_token, refresh_token, user: newUser } = response.data;

      setAuthTokens(access_token, refresh_token || null, JSON.stringify(newUser), rememberMe);
      setUser(newUser);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error: any) {
      const errorMessage = error?.response?.data?.error || error?.message || 'Erro no cadastro';
      return {
        success: false,
        message: typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage)
      };
    }
  };

  const loginWithAI = async () => {
    try {
      const response = await authAPI.login({
        email: 'demo@alca.fin',
        password: 'demo123'
      });
      const { access_token, refresh_token, user: userData } = response.data;
      setAuthTokens(access_token, refresh_token || null, JSON.stringify(userData), true);
      setUser(userData);
      setIsAuthenticated(true);
      return { success: true };
    } catch {
      try {
        const registerResponse = await authAPI.register({
          name: 'Demo User',
          email: 'demo@alca.fin',
          password: 'demo123'
        });
        const { access_token, refresh_token, user: userData } = registerResponse.data;
        setAuthTokens(access_token, refresh_token || null, JSON.stringify(userData), true);
        setUser(userData);
        setIsAuthenticated(true);
        return { success: true };
      } catch (registerError: any) {
        return {
          success: false,
          message: registerError?.response?.data?.error || 'Erro no login com IA'
        };
      }
    }
  };

  const logout = () => {
    clearAuthStorage();
    setUser(null);
    setIsAuthenticated(false);
  };

  const updateUser = (userData: User) => {
    setUser(userData);
    const payload = JSON.stringify(userData);
    if (sessionStorage.getItem('auth_token')) sessionStorage.setItem('user_data', payload);
    if (localStorage.getItem('auth_token')) localStorage.setItem('user_data', payload);
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