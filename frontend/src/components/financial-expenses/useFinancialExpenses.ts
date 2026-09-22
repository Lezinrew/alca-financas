import { useEffect, useRef, useState } from 'react';
import { financialExpensesAPI, type ExpenseOverview, type ExpenseQuery, type FinancialExpenseListResponse } from '../../utils/api';

interface Result<T> { data: T | null; loading: boolean; error: string }

/** Keyed results never present data from an earlier filter as the current totals. */
function useExpenseRequest<T>(key: string, enabled: boolean, request: (signal: AbortSignal) => Promise<{ data: T }>) {
  const requestRef = useRef(request);
  requestRef.current = request;
  const [state, setState] = useState<Result<T> & { key: string }>({ key: '', data: null, loading: false, error: '' });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let active = true;
    setState({ key, data: null, loading: true, error: '' });
    void requestRef.current(controller.signal).then(({ data }) => {
      if (active) setState({ key, data, loading: false, error: '' });
    }).catch(() => {
      if (active && !controller.signal.aborted) {
        setState({ key, data: null, loading: false, error: 'Não foi possível atualizar. Tente novamente.' });
      }
    });
    return () => { active = false; controller.abort(); };
  }, [key, enabled]);
  if (!enabled) return { data: null, loading: false, error: '' } as Result<T>;
  if (state.key !== key) return { data: null, loading: true, error: '' } as Result<T>;
  return { data: state.data, loading: state.loading, error: state.error };
}

export function useFinancialExpenses(filters: ExpenseQuery, page: number, revision: number, enabled: boolean) {
  const filterKey = JSON.stringify(filters);
  const list = useExpenseRequest<FinancialExpenseListResponse>(`${filterKey}:${page}:${revision}`, enabled,
    signal => financialExpensesAPI.list({ ...filters, page, limit: 25 }, { signal }));
  const overview = useExpenseRequest<ExpenseOverview>(`${filterKey}:${revision}`, enabled,
    async signal => {
      const response = await financialExpensesAPI.overview(filters, { signal });
      if (response.data.complete !== true) throw new Error('Incomplete overview');
      return response;
    });
  return { list, overview };
}

export function useGeneralOverview(filters: ExpenseQuery, revision: number, enabled: boolean) {
  const general = { ...filters, month: undefined, year: undefined };
  return useExpenseRequest<ExpenseOverview>(`${JSON.stringify(general)}:${revision}`, enabled,
    async signal => {
      const response = await financialExpensesAPI.overview(general, { signal });
      if (!response.data.complete) throw new Error('Incomplete overview');
      return response;
    });
}
