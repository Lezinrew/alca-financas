import { financialExpensesAPI } from './api';

export interface PayablesSummary {
  month: number;
  year: number;
  /** Mês por extenso em português, ex.: "setembro de 2026". */
  monthLabel: string;
  paidCount: number;
  /** Pendentes e parciais, incluindo as vencidas. */
  openCount: number;
  /** Subconjunto de openCount com vencimento anterior à data da consulta. */
  overdueCount: number;
  partialCount: number;
  canceledCount: number;
  /** Soma dos valores pagos registrados nas contas da competência (inclui parciais). */
  paidSum: number;
  openRemainingSum: number;
  expectedSum: number;
  totalInMonth: number;
}

export const formatMonthLabel = (month: number, year: number) =>
  new Date(year, month - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });

/**
 * Resumo de contas a pagar por competência, agregado no servidor sobre o conjunto
 * completo do mês (endpoint /financial-expenses/overview). Lança em caso de falha:
 * quem chama decide como mostrar a indisponibilidade, nunca como "zero".
 */
export async function loadPayablesSummary(month: number, year: number, signal?: AbortSignal): Promise<PayablesSummary> {
  const { data } = await financialExpensesAPI.overview({ month, year, reference_month: month, reference_year: year }, { signal });
  if (data.complete !== true) throw new Error('Resumo incompleto');
  return {
    month, year, monthLabel: formatMonthLabel(month, year),
    paidCount: data.counts.paid,
    openCount: data.counts.pending + data.counts.partial,
    overdueCount: data.counts.overdue,
    partialCount: data.counts.partial,
    canceledCount: data.counts.canceled,
    paidSum: data.paid,
    openRemainingSum: data.remaining,
    expectedSum: data.expected,
    totalInMonth: data.total,
  };
}

/** Compatibilidade com chamadores antigos: null significa "indisponível", nunca "sem contas". */
export async function fetchPayablesSummary(month: number, year: number): Promise<PayablesSummary | null> {
  try {
    return await loadPayablesSummary(month, year);
  } catch {
    return null;
  }
}
