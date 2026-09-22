import { transactionsAPI } from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import { TransactionFilterState } from '../../hooks/useTransactionFilters';
import { TransactionRecord } from '../../types/transaction';

export interface TransactionPagination {
  total: number;
  page: number;
  pages: number;
  limit?: number;
}

export interface TransactionListResult {
  rows: TransactionRecord[];
  pagination: TransactionPagination;
}

export interface TransactionFacets {
  categories: Array<{ id: string; name: string; count: number }>;
  accounts: Array<{ id: string; name: string; count: number }>;
  types: Array<{ type: string; count: number }>;
  responsible_persons?: Array<{ name: string; count: number }>;
  summary?: {
    paid_income: number;
    paid_expense: number;
    net_paid: number;
    transaction_count: number;
    uncategorized_count: number;
  };
}

/** Parâmetros de filtro enviados à API (sem paginação/ordenação). */
export const buildFilterParams = (filters: TransactionFilterState) => ({
  date_preset: filters.datePreset,
  date_from: filters.dateFrom,
  date_to: filters.dateTo,
  types: filters.types.join(','),
  type: filters.types.length === 1 ? filters.types[0] : undefined,
  account_ids: filters.accountIds.join(','),
  category_ids: filters.categoryIds.join(','),
  min_amount: filters.minAmount,
  max_amount: filters.maxAmount,
  search: filters.search,
  status: filters.status,
  is_recurring: filters.isRecurring,
});

/** O backend devolve `{data: [...], pagination: {...}}`; versões antigas devolviam o array direto. */
const normalizeList = (payload: unknown): TransactionListResult => {
  const raw = payload as { data?: unknown; pagination?: Partial<TransactionPagination> } | TransactionRecord[] | null;
  const rows: TransactionRecord[] = Array.isArray(raw) ? raw : Array.isArray(raw?.data) ? raw.data as TransactionRecord[] : [];
  const pagination = !Array.isArray(raw) && raw?.pagination && typeof raw.pagination.total === 'number'
    ? { total: raw.pagination.total, page: raw.pagination.page ?? 1, pages: Math.max(1, raw.pagination.pages ?? 1), limit: raw.pagination.limit }
    : { total: rows.length, page: 1, pages: 1 };
  return { rows, pagination };
};

/**
 * Lista e resumo (facets) das transações. Trocas rápidas de filtro descartam respostas
 * antigas; erro nunca vira lista vazia ou R$ 0,00. `revision` força uma nova consulta.
 */
export function useTransactions(filters: TransactionFilterState, revision: number, enabled: boolean) {
  const filterParams = buildFilterParams(filters);
  const facetKey = `${JSON.stringify(filterParams)}:${revision}`;
  const listKey = `${JSON.stringify(filters)}:${revision}`;
  const list = useKeyedRequest<TransactionListResult>(listKey, enabled, async (signal) => {
    const response = await transactionsAPI.getAll({ ...filterParams, page: filters.page, limit: filters.limit, sort: filters.sort }, { signal });
    return { data: normalizeList(response.data) };
  });
  const facets = useKeyedRequest<TransactionFacets>(facetKey, enabled, async (signal) => {
    const response = await transactionsAPI.getFacets(filterParams, { signal });
    if (!response.data || typeof response.data !== 'object') throw new Error('Facets indisponíveis');
    return { data: response.data as TransactionFacets };
  });
  return { list, facets };
}
