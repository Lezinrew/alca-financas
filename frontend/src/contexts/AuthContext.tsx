import { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { authAPI } from '../utils/api';

interface User {
  id: string;
  name: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (credentials: { email: string; password: string }) => Promise<{ success: boolean; message?: string }>;
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

  // Verifica se usuário está logado ao inicializar
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('auth_token');
      const userData = localStorage.getItem('user_data');

      if (token && userData) {
        try {
          // Tokens JWT reais começam com 'eyJ' (base64 de {")
          // Tokens fake são base64 de JSON com exp
          if (token.startsWith('eyJ')) {
            // Token JWT real - validar com servidor
            try {
              const response = await authAPI.getMe();
              setUser(response.data);
              setIsAuthenticated(true);
            } catch (error) {
              // Token inválido ou expirado
              throw new Error('Token inválido');
            }
          } else {
            // Token fake (base64) - verificar expiração localmente
            try {
              const tokenData = JSON.parse(atob(token));
              if (tokenData.exp && tokenData.exp < Date.now()) {
                throw new Error('Token expired');
              }
              // Use stored user data for fake tokens
              setUser(JSON.parse(userData));
              setIsAuthenticated(true);
            } catch (error) {
              // Token fake inválido ou expirado
              throw new Error('Token inválido');
            }
          }
        } catch (error) {
          // Token inválido, remove dados locais
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user_data');
          setUser(null);
          setIsAuthenticated(false);
        }
      } else {
        // Sem token ou userData
        setUser(null);
        setIsAuthenticated(false);
      }
      setLoading(false);
    };

    checkAuth();
  }, []);

  const login = async (credentials: { email: string; password: string }) => {
    try {
      const response = await authAPI.login(credentials);
      const { token, user: userData } = response.data;

      // Salva dados no localStorage
      localStorage.setItem('auth_token', token);
      localStorage.setItem('user_data', JSON.stringify(userData));

      setUser(userData);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error) {
      return {
        success: false,
        message: (error as any).response?.data?.error || 'Erro no login'
      };
    }
  };

  const register = async (userData: { name: string; email: string; password: string }) => {
    try {
      const response = await authAPI.register(userData);
      const { token, user: newUser } = response.data;

      // Salva dados no localStorage
      localStorage.setItem('auth_token', token);
      localStorage.setItem('user_data', JSON.stringify(newUser));

      setUser(newUser);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error) {
      return {
        success: false,
        message: (error as any).response?.data?.error || 'Erro no cadastro'
      };
    }
  };

  const loginWithAI = async () => {
    try {
      // Login com credenciais demo no backend real
      // Isso garante que o token seja válido e aceito pelo backend
      const response = await authAPI.login({
        email: 'demo@alca.fin',
        password: 'demo123'
      });

      const { token, user: userData } = response.data;

      // Salva dados no localStorage
      localStorage.setItem('auth_token', token);
      localStorage.setItem('user_data', JSON.stringify(userData));

      setUser(userData);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error) {
      // Se o login falhar, tenta criar o usuário demo
      try {
        const registerResponse = await authAPI.register({
          name: 'Demo User',
          email: 'demo@alca.fin',
          password: 'demo123'
        });

        const { token, user: userData } = registerResponse.data;

        localStorage.setItem('auth_token', token);
        localStorage.setItem('user_data', JSON.stringify(userData));

        setUser(userData);
        setIsAuthenticated(true);

        return { success: true };
      } catch (registerError) {
        return {
          success: false,
          message: (registerError as any).response?.data?.error || 'Erro no login com IA'
        };
      }
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    setUser(null);
    setIsAuthenticated(false);
  };

  const updateUser = (userData: User) => {
    setUser(userData);
    localStorage.setItem('user_data', JSON.stringify(userData));
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