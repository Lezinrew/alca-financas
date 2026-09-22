import { financialExpensesAPI, type ExpenseOverview, type ExpenseQuery, type FinancialExpenseListResponse } from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';

/** Mantido para compatibilidade: a implementação vive em hooks/useKeyedRequest. */
export { useKeyedRequest as useExpenseRequest } from '../../hooks/useKeyedRequest';

export function useFinancialExpenses(filters: ExpenseQuery, page: number, revision: number, enabled: boolean) {
  const filterKey = JSON.stringify(filters);
  const list = useKeyedRequest<FinancialExpenseListResponse>(`${filterKey}:${page}:${revision}`, enabled,
    signal => financialExpensesAPI.list({ ...filters, page, limit: 25 }, { signal }));
  const overview = useKeyedRequest<ExpenseOverview>(`${filterKey}:${revision}`, enabled,
    async signal => {
      const response = await financialExpensesAPI.overview(filters, { signal });
      if (response.data.complete !== true) throw new Error('Incomplete overview');
      return response;
    });
  return { list, overview };
}

export function useGeneralOverview(filters: ExpenseQuery, revision: number, enabled: boolean) {
  const general = { ...filters, month: undefined, year: undefined };
  return useKeyedRequest<ExpenseOverview>(`${JSON.stringify(general)}:${revision}`, enabled,
    async signal => {
      const response = await financialExpensesAPI.overview(general, { signal });
      if (!response.data.complete) throw new Error('Incomplete overview');
      return response;
    });
}
