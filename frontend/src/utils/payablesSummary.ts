import { financialExpensesAPI, type FinancialExpense } from './api';

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

function numExpense(v: unknown): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/** Resumo de contas a pagar por competência (mês/ano). */
export async function fetchPayablesSummary(month: number, year: number): Promise<PayablesSummary | null> {
  const ms = String(month);
  const ys = String(year);
  try {
    const [paidRes, openRes, overdueRes, cancelRes, sampleRes] = await Promise.all([
      financialExpensesAPI.list({ month: ms, year: ys, status: 'paid', page: 1, limit: 1 }),
      financialExpensesAPI.list({ month: ms, year: ys, outstanding_only: true, page: 1, limit: 1 }),
      financialExpensesAPI.list({ month: ms, year: ys, status: 'overdue', page: 1, limit: 1 }),
      financialExpensesAPI.list({ month: ms, year: ys, status: 'canceled', page: 1, limit: 1 }),
      financialExpensesAPI.list({ month: ms, year: ys, page: 1, limit: 300 }),
    ]);

    const paidCount = paidRes.data.pagination?.total ?? 0;
    const openCount = openRes.data.pagination?.total ?? 0;
    const overdueCount = overdueRes.data.pagination?.total ?? 0;
    const canceledCount = cancelRes.data.pagination?.total ?? 0;
    const rows: FinancialExpense[] = Array.isArray(sampleRes.data.data) ? sampleRes.data.data : [];
    const totalInMonth = sampleRes.data.pagination?.total ?? rows.length;
    const monthLabel = new Date(year, month - 1, 1).toLocaleDateString('pt-BR', {
      month: 'long',
      year: 'numeric',
    });

    let paidSumExpected = 0;
    let openRemainingSum = 0;
    for (const r of rows) {
      if (r.status === 'paid') {
        paidSumExpected += numExpense(r.amount_expected);
      }
      if (r.status === 'pending' || r.status === 'partial') {
        openRemainingSum += Math.max(0, numExpense(r.amount_expected) - numExpense(r.amount_paid));
      }
    }

    return {
      month,
      year,
      monthLabel,
      paidCount,
      openCount,
      overdueCount,
      canceledCount,
      paidSumExpected,
      openRemainingSum,
      totalInMonth,
      sampleSize: rows.length,
      sumsPartial: rows.length < totalInMonth,
    };
  } catch {
    return null;
  }
}
