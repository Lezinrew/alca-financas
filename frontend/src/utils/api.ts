import axios from 'axios';
import toast from 'react-hot-toast';
import { getAuthToken, clearAuthStorage } from './tokenStorage';

// Utilitário para remover barras duplicadas ao final
const trimTrailingSlashes = (value?: string) => value?.replace(/\/+$/, '') ?? '';

const DEFAULT_API_HOST = 'http://localhost:8001';

// Normaliza a URL base: deve ser absoluta (http/https). Evita ":8001" ou caminho relativo.
const resolveApiHost = (value?: string): string => {
  const trimmed = trimTrailingSlashes(value ?? '');
  if (!trimmed) return DEFAULT_API_HOST;
  // URL relativa ou só ":porta" → usar default
  if (!/^https?:\/\//i.test(trimmed)) return DEFAULT_API_HOST;
  if (trimmed.toLowerCase().endsWith('/api')) return trimmed.slice(0, -4);
  return trimmed;
};

// Configuração base da API (aceita VITE_API_URL ou REACT_APP_BACKEND_URL)
const API_HOST_URL = resolveApiHost(import.meta.env.VITE_API_URL || process.env.REACT_APP_BACKEND_URL);
const API_BASE_URL = `${API_HOST_URL}/api`;

// Instância do Axios com configurações padrão
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para adicionar token de autenticação (localStorage ou sessionStorage conforme Lembrar-me)
api.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor para tratar 401: sessão expirada → toast + limpar storage + redirect
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname;
      if (currentPath !== '/login' && currentPath !== '/register' && currentPath !== '/forgot-password' && !currentPath.startsWith('/reset-password')) {
        const token = getAuthToken();
        if (token) {
          clearAuthStorage();
          toast.error('Sua sessão expirou. Entre novamente.');
          window.location.href = '/login';
        }
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
  resetPassword: (token: string, newPassword: string) =>
    api.post('/auth/reset-password', { token, new_password: newPassword }),
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

// Funções de contas
export const accountsAPI = {
  getAll: () => api.get('/accounts'),
  getById: (id: string) => api.get(`/accounts/${id}`),
  create: (accountData: any) => api.post('/accounts', accountData),
  update: (id: string, accountData: any) => api.put(`/accounts/${id}`, accountData),
  delete: (id: string) => api.delete(`/accounts/${id}`),
  import: (cardId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/accounts/${cardId}/import`, formData, {
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
  account_id?: string;
}

// Funções de transações
export const transactionsAPI = {
  getAll: (filters: Record<string, any> = {}) => {
    const params = new URLSearchParams();
    Object.keys(filters).forEach(key => {
      // Só adiciona parâmetros que têm valor (não vazio, não null, não undefined)
      const value = filters[key];
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, String(value));
      }
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
    const searchParams = new URLSearchParams();
    // Só adiciona parâmetros que têm valor
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined && value !== '') {
        searchParams.append(key, String(value));
      }
    });
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
  googleLogin: () => `${API_BASE_URL}/auth/google/login`,
  microsoftLogin: () => `${API_BASE_URL}/auth/microsoft/login`,
  appleLogin: () => `${API_BASE_URL}/auth/apple/login`,
};

// Funções de Admin
export const adminAPI = {
  getStats: () => api.get('/admin/stats'),
  getUsers: (page = 1, perPage = 10, search = '') => api.get(`/admin/users?page=${page}&per_page=${perPage}&search=${search}`),
  getUserDetails: (id: string) => api.get(`/admin/users/${id}/details`),
  getLogs: (page = 1, perPage = 50) => api.get(`/admin/logs?page=${page}&per_page=${perPage}`),
  exportUserData: (id: string) => api.get(`/admin/users/${id}/export`, { responseType: 'blob' }),
  createUser: (userData: any) => api.post('/admin/users', userData),
  updateUserStatus: (id: string, data: { is_blocked?: boolean; is_admin?: boolean }) => api.put(`/admin/users/${id}`, data),
  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),
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