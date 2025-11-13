import { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { authAPI } from '../utils/api';

interface User {
  id: number;
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
          // Check if token is expired (for fake tokens)
          const tokenData = JSON.parse(atob(token));
          if (tokenData.exp && tokenData.exp < Date.now()) {
            throw new Error('Token expired');
          }

          // For real tokens, validate with server
          if (!token.startsWith('eyJ')) { // Not a base64 encoded fake token
            const response = await authAPI.getMe();
            setUser(response.data);
          } else {
            // Use stored user data for fake tokens
            setUser(JSON.parse(userData));
          }
          setIsAuthenticated(true);
        } catch (error) {
          // Token inválido, remove dados locais
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user_data');
          setUser(null);
          setIsAuthenticated(false);
        }
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
      // Simulated AI login with demo credentials
      const demoUser = {
        id: 1,
        name: 'Demo User',
        email: 'demo@alca.fin'
      };

      // Generate fake token with expiration
      const fakeToken = btoa(JSON.stringify({ 
        user: demoUser, 
        exp: Date.now() + (24 * 60 * 60 * 1000) // 24 hours 
      }));

      // Save to localStorage
      localStorage.setItem('auth_token', fakeToken);
      localStorage.setItem('user_data', JSON.stringify(demoUser));

      setUser(demoUser);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error) {
      return {
        success: false,
        message: 'Erro no login com IA'
      };
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