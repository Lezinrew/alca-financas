import axios from 'axios';
import toast from 'react-hot-toast';
import { clearAuthStorage, getAuthToken } from './tokenStorage';
import { supabase } from './supabaseClient';

// Utilitário para remover barras duplicadas ao final
const trimTrailingSlashes = (value?: string) => value?.replace(/\/+$/, '') ?? '';

// Em desenvolvimento, priorizamos mesma origem com proxy do Vite para reduzir preflight CORS.
const DEFAULT_API_HOST = '';

// Normaliza a URL base: se VITE_API_URL/REACT_APP_BACKEND_URL for uma URL absoluta (http/https),
// ela tem prioridade; caso contrário, usamos o fallback (DEFAULT_API_HOST).
const resolveApiHost = (value?: string): string => {
  const trimmed = trimTrailingSlashes(value ?? '');
  if (!trimmed) return DEFAULT_API_HOST;
  // Se não começar com http/https, consideramos inválido e caímos no fallback.
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

type LookupCacheEntry<T> = {
  ts: number;
  data: T;
  inFlight?: Promise<T>;
};

const LOOKUP_CACHE_TTL_MS = 60_000;
const lookupCache: {
  accounts?: LookupCacheEntry<any[]>;
  categories?: LookupCacheEntry<any[]>;
} = {};

const isLookupCacheValid = <T>(entry?: LookupCacheEntry<T>) =>
  !!entry && Date.now() - entry.ts < LOOKUP_CACHE_TTL_MS;

/** Limpa cache in-memory de listagens (ex.: após logout). */
export const invalidateLookupCache = (kind?: 'accounts' | 'categories') => {
  if (!kind || kind === 'accounts') lookupCache.accounts = undefined;
  if (!kind || kind === 'categories') lookupCache.categories = undefined;
};

// Interceptor para adicionar token de autenticação (localStorage ou sessionStorage conforme Lembrar-me)
api.interceptors.request.use(
  async (config) => {
    // Frontend não valida com secret; apenas repassa access_token do Supabase.
    // A validação da assinatura ocorre no backend via SUPABASE_JWT_SECRET.
    // Fonte de verdade: sessão do Supabase (Supabase-only).
    // Fallback: tokenStorage legado (se existir por algum motivo).
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token ?? getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor 401: tenta refresh do Supabase uma vez e repete o pedido; se continuar 401 → logout
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status;
    const original = error.config as typeof error.config & { _retry401?: boolean };

    if (status !== 401 || !original) {
      return Promise.reject(error);
    }

    const currentPath = window.location.pathname;
    const publicAuth =
      currentPath === '/login' ||
      currentPath === '/register' ||
      currentPath === '/forgot-password' ||
      currentPath.startsWith('/reset-password');

    if (publicAuth) {
      return Promise.reject(error);
    }

    if (!original._retry401) {
      original._retry401 = true;
      try {
        const { data, error: refreshErr } = await supabase.auth.refreshSession();
        if (!refreshErr && data.session?.access_token) {
          original.headers = original.headers ?? {};
          original.headers.Authorization = `Bearer ${data.session.access_token}`;
          return api.request(original);
        }
      } catch {
        /* logout abaixo */
      }
    }

    clearAuthStorage();
    invalidateLookupCache();
    await supabase.auth.signOut().catch(() => {});
    toast.error('Sessão inválida ou expirada. Entre novamente.');
    window.location.href = '/login';
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
  bootstrap: () => api.post('/auth/bootstrap'),
  updateSettings: (settings: any) => api.put('/auth/settings', settings),
  getSettings: () => api.get('/auth/settings'),
  exportBackup: () => api.get('/auth/backup/export'),
  importBackup: (backupData: any) => api.post('/auth/backup/import', backupData),
  clearAllData: () => api.post('/auth/data/clear'),
};

// Funções de categorias
export const categoriesAPI = {
  getAll: async (config?: { signal?: AbortSignal; skipCache?: boolean }) => {
    const canUseCache = !config?.skipCache && !config?.signal;
    if (canUseCache && isLookupCacheValid(lookupCache.categories)) {
      return { data: lookupCache.categories!.data };
    }
    if (canUseCache && lookupCache.categories?.inFlight) {
      const data = await lookupCache.categories.inFlight;
      return { data };
    }
    const request = api.get('/categories', config).then((response) => {
      const data = Array.isArray(response.data) ? response.data : (response.data?.data || []);
      lookupCache.categories = { ts: Date.now(), data };
      return data;
    });
    if (canUseCache) {
      lookupCache.categories = { ts: Date.now(), data: lookupCache.categories?.data || [], inFlight: request };
    }
    const data = await request.finally(() => {
      if (lookupCache.categories) {
        delete lookupCache.categories.inFlight;
      }
    });
    return { data };
  },
  create: async (categoryData: any) => {
    const response = await api.post('/categories', categoryData);
    invalidateLookupCache('categories');
    return response;
  },
  update: async (id: string, categoryData: any) => {
    const response = await api.put(`/categories/${id}`, categoryData);
    invalidateLookupCache('categories');
    return response;
  },
  delete: async (id: string) => {
    const response = await api.delete(`/categories/${id}`);
    invalidateLookupCache('categories');
    return response;
  },
  import: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/categories/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }).finally(() => invalidateLookupCache('categories'));
  },
};

// Funções de contas
export const accountsAPI = {
  getAll: async (config?: { signal?: AbortSignal; skipCache?: boolean }) => {
    const canUseCache = !config?.skipCache && !config?.signal;
    if (canUseCache && isLookupCacheValid(lookupCache.accounts)) {
      return { data: lookupCache.accounts!.data };
    }
    if (canUseCache && lookupCache.accounts?.inFlight) {
      const data = await lookupCache.accounts.inFlight;
      return { data };
    }
    const request = api.get('/accounts', config).then((response) => {
      const data = Array.isArray(response.data) ? response.data : (response.data?.data || []);
      lookupCache.accounts = { ts: Date.now(), data };
      return data;
    });
    if (canUseCache) {
      lookupCache.accounts = { ts: Date.now(), data: lookupCache.accounts?.data || [], inFlight: request };
    }
    const data = await request.finally(() => {
      if (lookupCache.accounts) {
        delete lookupCache.accounts.inFlight;
      }
    });
    return { data };
  },
  getById: (id: string) => api.get(`/accounts/${id}`),
  create: async (accountData: any) => {
    const response = await api.post('/accounts', accountData);
    invalidateLookupCache('accounts');
    return response;
  },
  update: async (id: string, accountData: any) => {
    const response = await api.put(`/accounts/${id}`, accountData);
    invalidateLookupCache('accounts');
    return response;
  },
  delete: async (id: string) => {
    const response = await api.delete(`/accounts/${id}`);
    invalidateLookupCache('accounts');
    return response;
  },
  import: (cardId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/accounts/${cardId}/import`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }).finally(() => invalidateLookupCache('accounts'));
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
  getFacets: (filters: Record<string, any> = {}) => {
    const params = new URLSearchParams();
    Object.keys(filters).forEach((key) => {
      const value = filters[key];
      if (value !== null && value !== undefined && value !== '') {
        params.append(key, String(value));
      }
    });
    return api.get(`/transactions/facets?${params.toString()}`);
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

// Planejamento — contrato da API (summary, expense_categories, income_categories, alerts)
export interface PlanningSummary {
  planned_income: number;
  planned_expenses: number;
  planned_balance: number;
  real_income: number;
  real_expenses: number;
  real_balance: number;
  savings_rate: number;
}

export interface PlanningExpenseCategory {
  category_id: string;
  category_name: string;
  category_color?: string;
  category_icon?: string;
  planned_amount: number;
  spent_amount: number;
  remaining_amount: number;
  progress_percent: number;
  status: 'safe' | 'warning' | 'exceeded' | 'unplanned';
}

export interface PlanningIncomeCategory {
  category_id: string;
  category_name: string;
  category_color?: string;
  category_icon?: string;
  planned_amount: number;
  received_amount: number;
  difference_amount: number;
  progress_percent: number;
  status: 'on_track' | 'below_target' | 'exceeded_target';
}

export interface PlanningAlert {
  type: string;
  category_id: string;
  category_name: string;
  spent_amount?: number;
  planned_amount?: number;
  savings_rate?: number;
}

export interface PlanningMonthResponse {
  period: { year: number; month: number };
  summary: PlanningSummary;
  expense_categories: PlanningExpenseCategory[];
  income_categories: PlanningIncomeCategory[];
  alerts: PlanningAlert[];
}

export interface PlanningCategoriesResponse {
  expense: Array<{ id: string; name: string; type: string; color: string; icon: string }>;
  income: Array<{ id: string; name: string; type: string; color: string; icon: string }>;
}

export const planningAPI = {
  getMonth: (month: number, year: number) =>
    api.get<PlanningMonthResponse>(`/planning/month?month=${month}&year=${year}`),
  saveMonth: (data: {
    month: number;
    year: number;
    planned_income: number;
    savings_percentage: number;
    category_plans: Array<{ category_id: string; planned_amount: number }>;
  }) => api.put('/planning/month', data),
  postMonthLines: (data: {
    month: number;
    year: number;
    lines: Array<{ category_id: string; planned_amount: number; notes?: string }>;
  }) => api.post('/planning/month', data),
  getMonthCategories: () => api.get<PlanningCategoriesResponse>('/planning/month/categories'),
  deletePlanLine: (planId: string) => api.delete(`/planning/month/${planId}`),
};

// Metas (Goals)
export interface Goal {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string;
  description?: string;
  target_amount: number;
  current_amount: number;
  target_date?: string;
  image_url?: string;
  status: 'active' | 'completed' | 'paused';
  created_at: string;
  updated_at: string;
  progress_percent?: number;
  remaining_amount?: number;
  months_remaining?: number | null;
  monthly_needed?: number | null;
}

export interface GoalContribution {
  id: string;
  goal_id: string;
  tenant_id: string;
  user_id: string;
  amount: number;
  date: string;
  source_type?: string;
  source_reference_id?: string;
  notes?: string;
  created_at: string;
}

export const goalsAPI = {
  list: (status?: string) =>
    api.get<Goal[]>(status ? `/goals?status=${status}` : '/goals'),
  get: (id: string) => api.get<Goal>(`/goals/${id}`),
  create: (data: {
    title: string;
    description?: string;
    target_amount: number;
    current_amount?: number;
    target_date?: string;
    image_url?: string;
    status?: string;
  }) => api.post<Goal>('/goals', data),
  update: (id: string, data: Partial<{
    title: string;
    description: string;
    target_amount: number;
    current_amount: number;
    target_date: string;
    image_url: string;
    status: string;
  }>) => api.put<Goal>(`/goals/${id}`, data),
  delete: (id: string) => api.delete(`/goals/${id}`),
  listContributions: (goalId: string) =>
    api.get<GoalContribution[]>(`/goals/${goalId}/contributions`),
  addContribution: (goalId: string, data: {
    amount: number;
    date?: string;
    source_type?: string;
    source_reference_id?: string;
    notes?: string;
  }) => api.post<GoalContribution>(`/goals/${goalId}/contributions`, data),
};

/** Contas a pagar (financial_expenses) */
export type FinancialExpenseStoredStatus = 'pending' | 'partial' | 'paid' | 'canceled';
export type FinancialExpenseDisplayStatus = FinancialExpenseStoredStatus | 'overdue';

export interface FinancialExpense {
  id: string;
  user_id: string;
  tenant_id: string;
  title: string;
  description?: string | null;
  category: string;
  subcategory?: string | null;
  amount_expected: number | string;
  amount_paid: number | string;
  due_date?: string | null;
  paid_at?: string | null;
  competency_month?: number | null;
  competency_year?: number | null;
  is_recurring: boolean;
  recurrence_type?: string | null;
  installment_current?: number | null;
  installment_total?: number | null;
  payment_method?: string | null;
  source_type?: string | null;
  responsible_person?: string | null;
  vehicle_name?: string | null;
  notes?: string | null;
  status: FinancialExpenseStoredStatus;
  is_overdue?: boolean;
  display_status?: FinancialExpenseDisplayStatus;
  created_at?: string;
  updated_at?: string;
}

export interface FinancialExpenseListResponse {
  data: FinancialExpense[];
  pagination: { total: number; page: number; per_page: number; pages: number };
}

export const financialExpensesAPI = {
  list: (filters: Record<string, string | number | boolean | undefined> = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        params.append(k, String(v));
      }
    });
    const q = params.toString();
    return api.get<FinancialExpenseListResponse>(`/financial-expenses${q ? `?${q}` : ''}`);
  },
  get: (id: string) => api.get<FinancialExpense>(`/financial-expenses/${id}`),
  create: (data: Record<string, unknown>) => api.post<FinancialExpense>('/financial-expenses', data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put<FinancialExpense>(`/financial-expenses/${id}`, data),
  delete: (id: string) => api.delete(`/financial-expenses/${id}`),
  markPaid: (id: string, body?: { amount_paid?: number; paid_at?: string }) =>
    api.post<FinancialExpense>(`/financial-expenses/${id}/mark-paid`, body ?? {}),
};

// Funções do dashboard
export const dashboardAPI = {
  getData: (month?: string, year?: string) => {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    return api.get(`/dashboard?${params.toString()}`);
  },
  getAdvanced: (month?: string, year?: string, showEvolution = true, config?: { signal?: AbortSignal }) => {
    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (year) params.append('year', year);
    if (showEvolution) params.append('show_evolution', 'true');
    return api.get(`/dashboard-advanced?${params.toString()}`, config);
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
  getUserStats: () => api.get('/admin/users/stats'),
  getInactiveUsers: (minDays = 30, limit = 200) =>
    api.get(`/admin/users/inactive?min_days=${minDays}&limit=${limit}`),
  getUsers: (page = 1, perPage = 10, search = '', status = 'all', adminsOnly = false) => {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      search: search || '',
    });
    if (status && status !== 'all') params.append('status', status);
    if (adminsOnly) params.append('admins_only', 'true');
    return api.get(`/admin/users?${params.toString()}`);
  },
  getUserDetails: (id: string) => api.get(`/admin/users/${id}/details`),
  getLogs: (page = 1, perPage = 50) => api.get(`/admin/logs?page=${page}&per_page=${perPage}`),
  exportUserData: (id: string) => api.get(`/admin/users/${id}/export`, { responseType: 'blob' }),
  createUser: (userData: any) => api.post('/admin/users', userData),
  updateUserStatus: (id: string, data: { is_blocked?: boolean; is_admin?: boolean }) =>
    api.put(`/admin/users/${id}`, data),
  patchUserRole: (id: string, role: string) => api.patch(`/admin/users/${id}/role`, { role }),
  patchUserStatus: (id: string, status: string) => api.patch(`/admin/users/${id}/status`, { status }),
  sendInactiveWarning: (id: string) => api.post(`/admin/users/${id}/send-inactive-warning`),
  sendBulkInactiveWarning: (userIds: string[]) =>
    api.post('/admin/users/send-bulk-inactive-warning', { user_ids: userIds }),
  reactivateUser: (id: string) => api.post(`/admin/users/${id}/reactivate`),
  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),
  purgeUser: (id: string, body: { confirm_email: string }) =>
    api.post(`/admin/users/${id}/purge`, body),
};

// Chatbot (Backend Flask) - caminho oficial nesta fase.
// Legado inativo: NÃO consumir /api/chat e /api/chat/ws.
export const chatbotAPI = {
  chat: (message: string, conversationId?: string) =>
    api.post('/chatbot/chat', { message, conversation_id: conversationId }),
  
  getConversation: (conversationId: string) =>
    api.get(`/chatbot/conversations/${conversationId}`),
  
  listConversations: () =>
    api.get('/chatbot/conversations'),
  
  deleteConversation: (conversationId: string) =>
    api.delete(`/chatbot/conversations/${conversationId}`),
  
  health: () =>
    api.get('/chatbot/health'),
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