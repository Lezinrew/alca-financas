import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export type TransactionFilterState = {
  datePreset:
    | 'today'
    | '7d'
    | 'this_month'
    | 'last_month'
    | 'last_90_days'
    | 'year_to_date'
    | 'custom';
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
  isRecurring?: boolean;
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
    // Primeiro tenta URL; se vazia, tenta último estado salvo em localStorage
    const hasUrlFilters =
      Array.from(searchParams.keys()).length > 0;
    const savedRaw = !hasUrlFilters
      ? window.localStorage.getItem('transactions_filters_v1')
      : null;
    const saved = savedRaw ? (JSON.parse(savedRaw) as Partial<TransactionFilterState>) : {};

    const get = (key: string) => searchParams.get(key) || (saved as any)?.[key];
    const urlTypes = parseList(searchParams.get('types'));
    const savedTypes = Array.isArray((saved as any)?.types)
      ? ((saved as any).types as string[])
      : parseList(((saved as any)?.types as string) || null);
    const urlAccountIds = parseList(searchParams.get('account_ids'));
    const savedAccountIds = Array.isArray((saved as any)?.accountIds)
      ? ((saved as any).accountIds as string[])
      : parseList(((saved as any)?.accountIds as string) || null);
    const urlCategoryIds = parseList(searchParams.get('category_ids'));
    const savedCategoryIds = Array.isArray((saved as any)?.categoryIds)
      ? ((saved as any).categoryIds as string[])
      : parseList(((saved as any)?.categoryIds as string) || null);

    return {
      datePreset:
        (searchParams.get('date_preset') as any) ||
        (saved.datePreset as any) ||
        'year_to_date',
      dateFrom: get('date_from') || undefined,
      dateTo: get('date_to') || undefined,
      types: (urlTypes.length ? urlTypes : savedTypes) as any,
      accountIds: urlAccountIds.length ? urlAccountIds : savedAccountIds,
      categoryIds: urlCategoryIds.length ? urlCategoryIds : savedCategoryIds,
      minAmount: get('min_amount')
        ? Number(get('min_amount'))
        : undefined,
      maxAmount: get('max_amount')
        ? Number(get('max_amount'))
        : undefined,
      search: get('search') || undefined,
      status: get('status') || undefined,
      isRecurring: get('is_recurring') === 'true' || undefined,
      page: Number(searchParams.get('page') || saved.page || 1),
      limit: Number(searchParams.get('limit') || saved.limit || 50),
      sort: searchParams.get('sort') || (saved.sort as string) || 'date:desc',
    };
  }, [searchParams]);

  const updateFilters = (partial: Partial<TransactionFilterState>) => {
    const next: TransactionFilterState = { ...filters, ...partial };

    const nextParams: Record<string, string> = {};

    if (next.datePreset !== 'year_to_date') nextParams.date_preset = next.datePreset;
    if (next.dateFrom) nextParams.date_from = next.dateFrom;
    if (next.dateTo) nextParams.date_to = next.dateTo;
    if (next.types.length) nextParams.types = next.types.join(',');
    if (next.accountIds.length) nextParams.account_ids = next.accountIds.join(',');
    if (next.categoryIds.length) nextParams.category_ids = next.categoryIds.join(',');
    if (next.minAmount != null) nextParams.min_amount = String(next.minAmount);
    if (next.maxAmount != null) nextParams.max_amount = String(next.maxAmount);
    if (next.search) nextParams.search = next.search;
    if (next.status) nextParams.status = next.status;
    if (next.isRecurring) nextParams.is_recurring = 'true';
    if (next.page !== 1) nextParams.page = String(next.page);
    if (next.limit !== 50) nextParams.limit = String(next.limit);
    if (next.sort !== 'date:desc') nextParams.sort = next.sort;

    setSearchParams(nextParams);

    // Persistência em localStorage (estado bruto)
    try {
      window.localStorage.setItem(
        'transactions_filters_v1',
        JSON.stringify(next),
      );
    } catch {
      // ignore
    }
  };

  const clearFilters = () => {
    try {
      window.localStorage.removeItem('transactions_filters_v1');
    } catch {
      // ignore
    }
    setSearchParams({});
  };

  return { filters, updateFilters, clearFilters };
}

