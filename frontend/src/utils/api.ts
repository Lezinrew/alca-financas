import axios from 'axios';

// Configuração base da API
// Suporta ambas as variáveis: VITE_API_URL (Vite) e REACT_APP_BACKEND_URL (fallback)
const API_BASE_URL = import.meta.env.VITE_API_URL || process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Instância do Axios com configurações padrão
const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para adicionar token de autenticação automaticamente
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor para tratar respostas e erros
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expirado ou inválido
      // Só redireciona se não estiver já na página de login
      const currentPath = window.location.pathname;
      if (currentPath !== '/login' && currentPath !== '/register') {
        // Verifica se há um token antes de remover (pode ser uma requisição antes do login)
        const token = localStorage.getItem('auth_token');
        if (token) {
          // Token existe mas é inválido - limpa e redireciona
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user_data');
          window.location.href = '/login';
        }
        // Se não há token, apenas rejeita o erro (pode ser uma requisição antes do login)
      }
    }
    return Promise.reject(error);
  }
);

// Funções de autenticação
export const authAPI = {
  login: (credentials: { email: string; password: string }) => api.post('/auth/login', credentials),
  register: (userData: { name: string; email: string; password: string }) => api.post('/auth/register', userData),
  forgotPassword: (email: string) => api.post('/auth/forgot-password', { email }),
  getMe: () => api.get('/auth/me'),
  updateSettings: (settings: any) => api.put('/auth/settings', settings),
  getSettings: () => api.get('/auth/settings'),
  exportBackup: () => api.get('/auth/backup/export'),
  importBackup: (backupData: any) => api.post('/auth/backup/import', backupData),
  clearAllData: () => api.post('/auth/data/clear'),
};

// Funções de categorias
export const categoriesAPI = {
  getAll: () => api.get('/categories'),
  create: (categoryData: any) => api.post('/categories', categoryData),
  update: (id: string, categoryData: any) => api.put(`/categories/${id}`, categoryData),
  delete: (id: string) => api.delete(`/categories/${id}`),
  import: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/categories/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

// Transaction types
export interface Transaction {
  id: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  category_id: string;
  date: string;
  status?: 'paid' | 'pending' | 'overdue' | 'cancelled';
  responsiblePerson?: string;
  is_recurring?: boolean;
  account_id?: string;
  installment_info?: {
    current: number;
    total: number;
    parent_id: string;
  };
}

export interface ReportItem {
  category_name?: string;
  category_color?: string;
  account_name?: string;
  account_color?: string;
  total?: number;
  percentage?: number;
  count?: number;
  current_balance?: number;
}

export interface ReportOverviewResponse {
  data: ReportItem[];
  total_amount?: number;
  period?: {
    month: number;
    year: number;
  };
}

interface ReportOverviewParams {
  month: string;
  year: string;
  type: string;
}

// Funções de transações
export const transactionsAPI = {
  getAll: (filters: Record<string, any> = {}) => {
    const params = new URLSearchParams();
    Object.keys(filters).forEach(key => {
      if (filters[key]) params.append(key, filters[key]);
    });
    return api.get(`/transactions?${params.toString()}`);
  },
  create: (transactionData: any) => api.post('/transactions', transactionData),
  update: (id: string, transactionData: any) => api.put(`/transactions/${id}`, transactionData),
  delete: (id: string) => api.delete(`/transactions/${id}`),
  import: (csvFile: File, accountId?: string) => {
    const formData = new FormData();
    formData.append('file', csvFile);
    if (accountId) {
      formData.append('account_id', accountId);
    }
    return api.post('/transactions/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

// Funções de relatórios
export const reportsAPI = {
  getOverview: (params: ReportOverviewParams) => {
    const searchParams = new URLSearchParams(Object.entries(params));
    return api.get<ReportOverviewResponse>(`/reports/overview?${searchParams.toString()}`);
  },
};

// Funções do dashboard
export const dashboardAPI = {
  getData: (month?: string, year?: string) => {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    return api.get(`/dashboard?${params.toString()}`);
  },
  getAdvanced: (month?: string, year?: string, showEvolution = true) => {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    if (showEvolution) params.append('show_evolution', 'true');
    return api.get(`/dashboard-advanced?${params.toString()}`);
  },
};

// Funções de OAuth
export const oauthAPI = {
  googleLogin: () => `${API_BASE_URL}/api/auth/google/login`,
  microsoftLogin: () => `${API_BASE_URL}/api/auth/microsoft/login`,
  appleLogin: () => `${API_BASE_URL}/api/auth/apple/login`,
};

// Utilitários
export const formatCurrency = (value: number, currency = 'BRL') => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: currency,
  }).format(value);
};

export const formatDate = (date: string | Date) => {
  return new Date(date).toLocaleDateString('pt-BR');
};

export const formatDateTime = (date: string | Date) => {
  return new Date(date).toLocaleString('pt-BR');
};

export const formatPercent = (value: number): string => {
  const signal = value >= 0 ? '+' : '';
  return `${signal}${value.toFixed(1)}%`;
};

export default api;