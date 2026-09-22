/**
 * Parser único de moeda das Metas. Aceita "1.500,00", "1500,50", "1500.50",
 * "R$ 1.500", "1500". Retorna 0 para vazio ou inválido; nunca lança.
 */
export function parseGoalAmount(value: string | null | undefined): number {
  if (!value) return 0;
  const cleaned = value.replace(/\s/g, '').replace(/R\$/gi, '');
  if (!cleaned || !/^-?[\d.,]+$/.test(cleaned)) return 0;
  const lastComma = cleaned.lastIndexOf(',');
  const lastDot = cleaned.lastIndexOf('.');
  let normalized: string;
  if (lastComma >= 0 && lastDot >= 0) {
    // Ambos presentes: o último separador é o decimal, o outro é milhar.
    normalized = lastComma > lastDot
      ? cleaned.replace(/\./g, '').replace(',', '.')
      : cleaned.replace(/,/g, '');
  } else if (lastComma >= 0) {
    normalized = cleaned.replace(/\./g, '').replace(',', '.');
  } else if (lastDot >= 0) {
    const dots = cleaned.split('.').length - 1;
    const decimals = cleaned.length - lastDot - 1;
    // "1.500" (um ponto, três dígitos) é milhar em pt-BR; "1500.50" e "1.5" são decimais.
    normalized = dots > 1 || decimals === 3 ? cleaned.replace(/\./g, '') : cleaned;
  } else {
    normalized = cleaned;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

export const GOAL_AMOUNT_ERROR = 'Informe um valor maior que zero';
export const GOALS_LOAD_ERROR = 'Não foi possível carregar as metas. Tente novamente.';
export const GOAL_LOAD_ERROR = 'Não foi possível carregar a meta. Tente novamente.';
export const GOAL_SAVE_ERROR = 'Não foi possível salvar a meta. Tente novamente.';
export const GOAL_CONTRIBUTION_ERROR = 'Não foi possível registrar o aporte. Tente novamente.';
export const GOAL_DELETE_ERROR = 'Não foi possível excluir a meta. Tente novamente.';

/** Mensagem do backend, quando existir e for legível; nunca a mensagem técnica do erro. */
export function goalApiMessage(err: unknown): string | undefined {
  const data = (err as { response?: { data?: { error?: unknown; message?: unknown } } })?.response?.data;
  const text = data?.error ?? data?.message;
  return typeof text === 'string' && text.trim() ? text : undefined;
}

export function isNotFound(err: unknown): boolean {
  return (err as { response?: { status?: number } })?.response?.status === 404;
}
