import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export type TransactionFilterState = {
  datePreset: 'today' | '7d' | 'this_month' | 'last_month' | 'custom';
  dateFrom?: string;
  dateTo?: string;
  types: ('income' | 'expense' | 'transfer')[];
  accountIds: string[];
  categoryIds: string[];
  minAmount?: number;
  maxAmount?: number;
  search?: string;
  method?: string;
  status?: string;
  page: number;
  limit: number;
  sort: string;
};

const parseList = (raw: string | null): string[] =>
  (raw || '')
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);

export function useTransactionFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters: TransactionFilterState = useMemo(() => {
    return {
      datePreset: (searchParams.get('date_preset') as any) || 'this_month',
      dateFrom: searchParams.get('date_from') || undefined,
      dateTo: searchParams.get('date_to') || undefined,
      types: parseList(searchParams.get('types')) as any,
      accountIds: parseList(searchParams.get('account_ids')),
      categoryIds: parseList(searchParams.get('category_ids')),
      minAmount: searchParams.get('min_amount')
        ? Number(searchParams.get('min_amount'))
        : undefined,
      maxAmount: searchParams.get('max_amount')
        ? Number(searchParams.get('max_amount'))
        : undefined,
      search: searchParams.get('search') || undefined,
      method: searchParams.get('method') || undefined,
      status: searchParams.get('status') || undefined,
      page: Number(searchParams.get('page') || 1),
      limit: Number(searchParams.get('limit') || 50),
      sort: searchParams.get('sort') || 'date:desc',
    };
  }, [searchParams]);

  const updateFilters = (partial: Partial<TransactionFilterState>) => {
    const next: TransactionFilterState = { ...filters, ...partial };

    const nextParams: Record<string, string> = {};

    if (next.datePreset !== 'this_month') nextParams.date_preset = next.datePreset;
    if (next.dateFrom) nextParams.date_from = next.dateFrom;
    if (next.dateTo) nextParams.date_to = next.dateTo;
    if (next.types.length) nextParams.types = next.types.join(',');
    if (next.accountIds.length) nextParams.account_ids = next.accountIds.join(',');
    if (next.categoryIds.length) nextParams.category_ids = next.categoryIds.join(',');
    if (next.minAmount != null) nextParams.min_amount = String(next.minAmount);
    if (next.maxAmount != null) nextParams.max_amount = String(next.maxAmount);
    if (next.search) nextParams.search = next.search;
    if (next.method) nextParams.method = next.method;
    if (next.status) nextParams.status = next.status;
    if (next.page !== 1) nextParams.page = String(next.page);
    if (next.limit !== 50) nextParams.limit = String(next.limit);
    if (next.sort !== 'date:desc') nextParams.sort = next.sort;

    setSearchParams(nextParams);
  };

  const clearFilters = () => {
    setSearchParams({});
  };

  return { filters, updateFilters, clearFilters };
}

