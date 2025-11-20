import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const normalizeBaseUrl = (value?: string | null) => {
  if (!value) return 'http://localhost:8001';
  return value.replace(/\/+$/, '');
};

const API_BASE_URL = normalizeBaseUrl(process.env.EXPO_PUBLIC_API_URL);

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para adicionar token
api.interceptors.request.use(
  async (config) => {
    const token = await AsyncStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor para tratar erros
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      await AsyncStorage.removeItem('auth_token');
      await AsyncStorage.removeItem('user_data');
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (credentials: { email: string; password: string }) =>
    api.post('/auth/login', credentials),
  register: (userData: { name: string; email: string; password: string }) =>
    api.post('/auth/register', userData),
  getMe: () => api.get('/auth/me'),
};

// Dashboard API
export const dashboardAPI = {
  getData: (month?: string, year?: string) => {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    return api.get(`/dashboard?${params.toString()}`);
  },
};

// Transactions API
export const transactionsAPI = {
  getAll: (filters: Record<string, any> = {}) => {
    const params = new URLSearchParams();
    Object.keys(filters).forEach(key => {
      if (filters[key]) params.append(key, filters[key]);
    });
    return api.get(`/transactions?${params.toString()}`);
  },
  create: (transactionData: any) => api.post('/transactions', transactionData),
  update: (id: string, transactionData: any) =>
    api.put(`/transactions/${id}`, transactionData),
  delete: (id: string) => api.delete(`/transactions/${id}`),
};

// Accounts API
export const accountsAPI = {
  getAll: () => api.get('/accounts'),
  create: (accountData: any) => api.post('/accounts', accountData),
  update: (id: string, accountData: any) =>
    api.put(`/accounts/${id}`, accountData),
  delete: (id: string) => api.delete(`/accounts/${id}`),
};

// Categories API
export const categoriesAPI = {
  getAll: () => api.get('/categories'),
};

// Utils
export const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value);
};

export const formatDate = (date: string | Date) => {
  return new Date(date).toLocaleDateString('pt-BR');
};

export default api;
