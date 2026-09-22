import { CreditCard } from '../../types/credit-card';

/** Conta da API (`/accounts`) no formato mínimo usado pelos cartões. */
export interface AccountRecord {
  id: string;
  name: string;
  type?: string;
  is_active?: boolean;
  limit?: number | null;
  initial_balance?: number | null;
  current_balance?: number | null;
  closing_day?: number | null;
  due_day?: number | null;
  color?: string | null;
  icon?: string | null;
  account_id?: string | null;
  card_type?: string | null;
}

export interface Period { dateFrom: string; dateTo: string }

/** Converte uma conta `credit_card` no formato de cartão usado na UI. */
export function accountToCreditCard(acc: AccountRecord): CreditCard {
  // Limite total: usa 'limit' se disponível, senão 'initial_balance'.
  const limit = acc.limit ?? acc.initial_balance ?? 0;
  // current_balance representa o gasto (negativo ou positivo); o valor usado é sempre o absoluto.
  const used = Math.abs(acc.current_balance ?? 0);
  return {
    id: acc.id,
    name: acc.name,
    limit,
    used,
    available: limit - used,
    closingDay: acc.closing_day || 10,
    dueDay: acc.due_day || 15,
    color: acc.color || '#6366f1',
    icon: acc.icon || 'credit-card',
    is_active: acc.is_active,
    account_id: acc.account_id ?? undefined,
    card_type: acc.card_type ?? undefined,
  };
}

export function toISODate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/** Fatura aberta atual: do dia após o último fechamento até o próximo fechamento (inclusive). */
export function computeCurrentBillPeriod(closingDay: number, today = new Date()): Period {
  const y = today.getFullYear();
  const m = today.getMonth();
  const thisClosing = new Date(y, m, closingDay);
  let start: Date;
  let end: Date;
  if (today <= thisClosing) {
    end = thisClosing;
    const prevClosing = new Date(y, m - 1, closingDay);
    start = new Date(prevClosing);
    start.setDate(prevClosing.getDate() + 1);
  } else {
    end = new Date(y, m + 1, closingDay);
    start = new Date(thisClosing);
    start.setDate(thisClosing.getDate() + 1);
  }
  return { dateFrom: toISODate(start), dateTo: toISODate(end) };
}

export function computeMonthPeriod(month: number, year: number): Period {
  return { dateFrom: toISODate(new Date(year, month - 1, 1)), dateTo: toISODate(new Date(year, month, 0)) };
}

export function getNextClosingDate(closingDay: number, today = new Date()): Date {
  const closingDate = new Date(today.getFullYear(), today.getMonth(), closingDay);
  if (today > closingDate) closingDate.setMonth(today.getMonth() + 1);
  return closingDate;
}

export function getDaysUntilClosing(closingDay: number, today = new Date()): number {
  const diff = getNextClosingDate(closingDay, today).getTime() - today.getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

export function getNextDueDate(card: Pick<CreditCard, 'closingDay' | 'dueDay'>, today = new Date()): Date {
  const closingDate = getNextClosingDate(card.closingDay, today);
  const dueDate = new Date(closingDate);
  dueDate.setDate(dueDate.getDate() + (card.dueDay - card.closingDay));
  if (dueDate.getDate() < card.dueDay) {
    dueDate.setMonth(dueDate.getMonth() + 1);
    dueDate.setDate(card.dueDay);
  }
  return dueDate;
}

export const MONTH_NAMES = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];

/** Rótulo e classe de situação de um lançamento; pendente nunca aparece como pago. */
export function expenseStatus(status?: string): { label: string; className: string } {
  if (status === 'paid') return { label: 'Pago', className: 'cc-badge cc-badge-paid' };
  if (status === 'canceled' || status === 'cancelled') return { label: 'Cancelado', className: 'cc-badge cc-badge-canceled' };
  return { label: 'Pendente', className: 'cc-badge cc-badge-pending' };
}

/** Lê a mensagem de erro devolvida pela API, quando existir. */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === 'object') {
    const response = (err as { response?: { data?: { error?: unknown; message?: unknown } } }).response;
    const body = response?.data;
    if (body && typeof body.error === 'string') return body.error;
    if (body && typeof body.message === 'string') return body.message;
    if (err instanceof Error && err.message) return err.message;
  }
  return fallback;
}
