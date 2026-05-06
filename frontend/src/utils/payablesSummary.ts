import api from './api';

export interface PayablesSummary {
  month: number;
  year: number;
  monthLabel: string;
  paidCount: number;
  openCount: number;
  overdueCount: number;
  canceledCount: number;
  paidSumExpected: number;
  openRemainingSum: number;
  totalInMonth: number;
  sampleSize: number;
  sumsPartial: boolean;
}

/**
 * Resumo de contas a pagar por competência (mês/ano).
 *
 * OTIMIZAÇÃO: Usa endpoint consolidado /api/financial-expenses/summary
 * que retorna todos os contadores em 1 única requisição ao invés de 5.
 */
export async function fetchPayablesSummary(month: number, year: number): Promise<PayablesSummary | null> {
  try {
    const response = await api.get(`/financial-expenses/summary?month=${month}&year=${year}`);
    const data = response.data;

    // Mapeia campos do backend para interface do frontend (snake_case → camelCase)
    return {
      month: data.month,
      year: data.year,
      monthLabel: data.month_label || `${month}/${year}`,
      paidCount: data.paid_count ?? 0,
      openCount: data.open_count ?? 0,
      overdueCount: data.overdue_count ?? 0,
      canceledCount: data.canceled_count ?? 0,
      paidSumExpected: data.paid_sum_expected ?? 0,
      openRemainingSum: data.open_remaining_sum ?? 0,
      totalInMonth: data.total_in_month ?? 0,
      sampleSize: data.sample_size ?? 0,
      sumsPartial: data.sums_partial ?? false,
    };
  } catch (error) {
    console.error('Erro ao buscar resumo de contas a pagar:', error);
    return null;
  }
}
