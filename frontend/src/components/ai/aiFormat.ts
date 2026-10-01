import type {
  AiRun, Fact, FactPeriod, LedgerState, ProgressStage, ProposalEffect, ProposalKind, ProposalStatus, RunStatus, RunTask, SpaceKind,
} from './aiTypes';

/**
 * Formatação da tela do operador.
 *
 * Regra central: valor monetário é formatado a partir da STRING decimal, por
 * manipulação de texto. Não passa por `Number()` porque:
 *  - `Number(x) || 0` transforma ausência e lixo em "R$ 0,00" (um saldo falso);
 *  - `number` perde centavos acima de ~9 quatrilhões e arredonda o que não devia.
 * Quando não dá para formatar, a função devolve `null` e a tela mostra travessão
 * com o motivo, nunca zero.
 */

const DECIMAL = /^(-)?(\d+)(?:\.(\d+))?$/;
const NBSP = '\u00a0';
const CURRENCY_SYMBOLS: Record<string, string> = { BRL: 'R$', USD: 'US$', EUR: '€' };
export const DASH = '—';

const groupThousands = (digits: string) => digits
  .replace(/^0+(?=\d)/, '')
  .replace(/\B(?=(\d{3})+(?!\d))/g, '.');

/** `"1250.00"` -> `"R$ 1.250,00"`. Devolve `null` se não for decimal em string. */
export const formatDecimalMoney = (value: unknown, currency?: string | null): string | null => {
  if (typeof value !== 'string') return null;
  const match = DECIMAL.exec(value.trim());
  if (!match) return null;
  const [, sign, integer, fraction = ''] = match;
  // Menos de duas casas completa com zero; mais de duas é preservado como veio
  // (arredondar aqui seria fazer conta no frontend, o que é papel do backend).
  const cents = fraction.length >= 2 ? fraction : fraction.padEnd(2, '0');
  const code = (currency || 'BRL').toUpperCase();
  const symbol = CURRENCY_SYMBOLS[code] ?? code;
  const isZero = /^0+$/.test(integer) && /^0*$/.test(fraction);
  return `${sign && !isZero ? '-' : ''}${symbol}${NBSP}${groupThousands(integer)},${cents}`;
};

export const formatCount = (value: unknown): string | null => {
  // Contagem pode vir como inteiro JSON; inteiro seguro não perde precisão.
  if (typeof value === 'number' && Number.isSafeInteger(value)) return `${value < 0 ? '-' : ''}${groupThousands(String(Math.abs(value)))}`;
  if (typeof value !== 'string') return null;
  const match = /^(-)?(\d+)$/.exec(value.trim());
  return match ? `${match[1] ?? ''}${groupThousands(match[2])}` : null;
};

/** Data civil `AAAA-MM-DD` -> `DD/MM/AAAA`, sem `Date` (evita o dia anterior por fuso). */
export const formatCivilDate = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : null;
};

const instantFormatter = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
});

/** Instante UTC -> data e hora no fuso de apresentação do contrato (America/Sao_Paulo). */
export const formatInstant = (value: unknown): string | null => {
  if (typeof value !== 'string' || !value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return instantFormatter.format(date).replace(',', ' às');
};

export const formatPeriod = (period?: FactPeriod | { start?: string | null; end?: string | null } | null): string | null => {
  if (!period) return null;
  if ('label' in period && period.label) return period.label;
  const start = formatCivilDate(period.start);
  const end = formatCivilDate(period.end);
  if (start && end) return start === end ? start : `${start} a ${end}`;
  return start ?? end;
};

export interface FactDisplay {
  text: string;
  /** Preenchido quando não há valor exibível: explica o travessão. */
  missing: string | null;
}

/** Valor de um fato pronto para a tela. Ausência vira travessão + motivo. */
export const formatFactValue = (fact: Pick<Fact, 'value' | 'unit' | 'currency' | 'missing_reason'>): FactDisplay => {
  if (fact.value === null || fact.value === undefined) {
    return { text: DASH, missing: fact.missing_reason?.trim() || 'O servidor não informou o motivo.' };
  }
  let text: string | null;
  if (fact.unit === 'money') text = formatDecimalMoney(fact.value, fact.currency);
  else if (fact.unit === 'count') text = formatCount(fact.value);
  else if (fact.unit === 'date') text = formatCivilDate(fact.value);
  else text = typeof fact.value === 'string' && fact.value.trim() ? fact.value : null;
  return text === null
    ? { text: DASH, missing: 'O valor veio em um formato que a tela não reconhece.' }
    : { text, missing: null };
};

const SPACE_KIND: Record<string, string> = { personal: 'Pessoal', business: 'Negócio', family: 'Família' };
export const spaceKindLabel = (kind?: SpaceKind | null) => (kind && SPACE_KIND[kind]) || 'Tipo não informado';

const RUN_STATUS: Record<RunStatus, string> = {
  queued: 'Na fila', running: 'Em andamento', waiting_review: 'Aguardando revisão', completed: 'Concluída',
  failed: 'Falhou', cancelled: 'Cancelada', needs_reconciliation: 'Em conferência',
};
export const runStatusLabel = (status: RunStatus) => RUN_STATUS[status] ?? 'Situação desconhecida';

const TASKS: Record<string, string> = {
  finance_question: 'Pergunta sobre finanças', statement_import: 'Extrato do e-mail',
  apply_proposal: 'Aplicação de proposta', reverse_operation: 'Desfazer operação',
};
export const taskLabel = (task: RunTask) => TASKS[task] ?? 'Tarefa';

const PROPOSAL_KIND: Record<string, string> = {
  payable_payment: 'Baixa em conta a pagar', statement_import: 'Importação de extrato', reverse_operation: 'Compensação (desfazer)',
};
export const proposalKindLabel = (kind?: ProposalKind | null) => (kind && PROPOSAL_KIND[kind]) || 'Alteração';

const PROPOSAL_STATUS: Record<ProposalStatus, string> = {
  draft: 'Rascunho', ready: 'Pronta para revisão', approved: 'Aprovada', applied: 'Aplicada',
  rejected: 'Rejeitada', expired: 'Expirada', stale: 'Desatualizada',
};
export const proposalStatusLabel = (status: ProposalStatus) => PROPOSAL_STATUS[status] ?? 'Situação desconhecida';

const PAYABLE_STATUS: Record<string, string> = {
  pending: 'Pendente', partial: 'Parcial', paid: 'Paga', overdue: 'Vencida', canceled: 'Cancelada', cancelled: 'Cancelada',
};
export const payableStatusLabel = (status?: string | null) => (status ? PAYABLE_STATUS[status] ?? status : DASH);

const SOURCE_KIND: Record<string, string> = {
  sql: 'Dados do aplicativo', artifact: 'Arquivo', email: 'E-mail', rag: 'Documento', proposal: 'Proposta', operation: 'Operação',
};
export const sourceKindLabel = (kind?: string | null) => (kind && SOURCE_KIND[kind]) || 'Fonte';

const ORIGIN_KIND: Record<string, string> = { email: 'E-mail', upload: 'Arquivo enviado', whatsapp: 'WhatsApp', manual: 'Lançamento manual' };
export const originKindLabel = (kind?: string | null) => (kind && ORIGIN_KIND[kind]) || 'Origem não informada';

const EVIDENCE_KIND: Record<string, string> = {
  ofx_transaction: 'Transação do extrato (OFX)', receipt: 'Comprovante', email: 'E-mail', manual: 'Informação manual',
};
export const evidenceKindLabel = (kind?: string | null) => (kind && EVIDENCE_KIND[kind]) || 'Evidência';

/**
 * Rótulos dos totais de uma importação. As quatro primeiras chaves são as que o
 * backend emite (`finance/proposals.py`); as demais são sinônimos tolerados.
 * Chave desconhecida vira um rótulo genérico em português: mostrar o nome cru do
 * campo ("transfer skipped") seria vazar o formato interno para o titular.
 */
const TOTALS: Record<string, string> = {
  income: 'Entradas', expense: 'Saídas', net: 'Saldo do período', transfer_skipped: 'Transferências não importadas',
  credits: 'Entradas', debits: 'Saídas', amount: 'Valor total',
  new_amount: 'Valor dos itens novos', duplicate_amount: 'Valor dos duplicados', count: 'Itens',
};
export const totalLabel = (key: string) => TOTALS[key] ?? `Outro total (${key.replace(/_/g, ' ')})`;

/**
 * Um total pode ser dinheiro (string decimal com casas, "310.00") ou contagem
 * (inteiro). Sem a distinção, "3 itens" apareceria como "R$ 3,00". Ausência ou
 * formato estranho vira travessão, nunca zero.
 */
export const formatTotalValue = (value: unknown): string =>
  (typeof value === 'string' && value.includes('.') ? formatDecimalMoney(value) : formatCount(value)) ?? DASH;

/** Totais de um efeito, na ordem em que o servidor mandou: `[rótulo, valor formatado]`. */
export const effectTotals = (effect?: ProposalEffect | null): Array<[string, string]> =>
  Object.entries(effect?.totals ?? {}).map(([key, value]): [string, string] => [totalLabel(key), formatTotalValue(value)]);

const isZeroCount = (value: unknown) => value === 0 || (typeof value === 'string' && /^0+$/.test(value.trim()));

/**
 * Contagens de itens de um efeito, já rotuladas: `[rótulo, valor formatado]`.
 *
 * O backend manda os campos de contagem em TODO efeito. Numa baixa (ou na
 * compensação de uma baixa) eles vêm zerados e não significam nada: mostrar
 * "Itens novos: 0" ao lado de um pagamento confundiria. Por isso zero só
 * aparece quando o efeito é uma importação, em que "0 duplicados" é informação.
 * Numa compensação de importação, `items_new` é a quantidade de lançamentos que
 * serão cancelados, não "itens novos".
 */
export const effectCounts = (effect?: ProposalEffect | null, applied = false): Array<[string, string]> => {
  if (!effect) return [];
  const snapshot = !!(effect.before || effect.after);
  const reversal = effect.state_after === 'revertido';
  const rows: Array<[string, string]> = [];
  const add = (label: string, value: unknown) => {
    if (value == null) return;
    if ((snapshot || reversal) && isZeroCount(value)) return;
    rows.push([label, formatCount(value) ?? DASH]);
  };
  if (reversal) add(applied ? 'Lançamentos cancelados' : 'Lançamentos que serão cancelados', effect.items_new);
  else add(applied ? 'Itens importados' : 'Itens novos', effect.items_new);
  add(applied ? 'Duplicados (não importados)' : 'Duplicados (não serão importados)', effect.items_duplicate);
  add(applied ? 'Transferências (não importadas)' : 'Transferências (não serão importadas)', effect.items_transfer_skipped);
  return rows;
};

export interface LedgerStateInfo {
  id: LedgerState;
  label: string;
  explanation: string;
}

/**
 * Os três estados que o titular não pode confundir (contrato, seção 12).
 * A ordem vai do mais fraco ao mais forte: revisar evidência, registrar no
 * aplicativo, confirmar contra o extrato do banco.
 */
export const LEDGER_STATES: LedgerStateInfo[] = [
  { id: 'conferido', label: 'Conferido', explanation: 'A evidência (por exemplo, um comprovante) foi revisada. A conta continua em aberto: não é baixa.' },
  { id: 'registrado_pago', label: 'Registrado pago', explanation: 'O pagamento foi lançado no aplicativo, sem vínculo com o extrato do banco.' },
  { id: 'conciliado', label: 'Conciliado no extrato', explanation: 'O pagamento está ligado a uma transação que veio do extrato do banco (OFX).' },
];
// Estados que não fazem parte do trio acima, mas chegam em `effect.state_after`.
const OTHER_STATES: LedgerStateInfo[] = [
  { id: 'importado', label: 'Importado', explanation: 'As transações do extrato entram no aplicativo.' },
  // Compensação ("Desfazer"): o backend manda `revertido`. O histórico é preservado.
  { id: 'revertido', label: 'Desfeito', explanation: 'A operação original foi compensada. O histórico é preservado; nada é apagado.' },
];

export const ledgerStateInfo = (state?: LedgerState | null): LedgerStateInfo | null => {
  if (!state) return null;
  return [...LEDGER_STATES, ...OTHER_STATES].find(item => item.id === state) ?? null;
};

export type StageState = 'done' | 'current' | 'waiting' | 'pending' | 'failed' | 'cancelled';
export interface StageView {
  id: string;
  label: string;
  state: StageState;
}

const STAGE_STATE_TEXT: Record<StageState, string> = {
  done: 'concluída', current: 'em andamento', waiting: 'aguardando você', pending: 'a seguir', failed: 'falhou', cancelled: 'cancelada',
};
export const stageStateText = (state: StageState) => STAGE_STATE_TEXT[state];

/**
 * Monta a trilha "buscando -> lendo -> preparando -> aguardando revisão ->
 * aplicado" a partir do que o servidor informou em `progress.stage`.
 *
 * Nada aqui avança sozinho: a etapa atual é sempre a que o servidor declarou.
 * Etapas que não fazem parte da tarefa são omitidas em vez de aparecerem como
 * "concluídas" (uma pergunta não passa por revisão nem aplica nada), e o rótulo
 * final só diz "Aplicado" quando existe, ou ainda pode existir, uma gravação.
 */
export const buildStages = (run: Pick<AiRun, 'status' | 'task' | 'progress' | 'proposal_ids' | 'operation_ids'>): StageView[] => {
  const writes = run.task === 'apply_proposal' || run.task === 'reverse_operation';
  const hasProposal = (run.proposal_ids?.length ?? 0) > 0;
  const hasOperation = (run.operation_ids?.length ?? 0) > 0;
  const finished = run.status === 'completed';
  const reported = run.progress?.stage ?? null;
  // Sem etapa informada, a única coisa honesta a dizer vem do estado da execução.
  const stage: ProgressStage | null = reported ?? (run.status === 'waiting_review' ? 'waiting_review' : null);
  const withReview = writes || hasProposal || run.task === 'statement_import' || stage === 'waiting_review' || stage === 'applying';
  const applied = writes || hasOperation || stage === 'applying';

  let lastLabel = 'Concluído';
  if (applied) lastLabel = 'Aplicado';
  // Revisão encerrada sem gravação (proposta rejeitada ou expirada): não dizer "Aplicado".
  else if (withReview) lastLabel = finished ? 'Revisão encerrada' : 'Aplicado';

  const visible: Array<{ id: ProgressStage; label: string }> = [];
  if (!writes) visible.push({ id: 'searching', label: 'Buscando' }, { id: 'reading', label: 'Lendo' }, { id: 'preparing', label: 'Preparando' });
  if (withReview) visible.push({ id: 'waiting_review', label: 'Aguardando revisão' });
  visible.push({ id: 'done', label: lastLabel });

  // "applying" não tem coluna própria: é a última etapa ainda em andamento.
  const position = stage === null ? -1 : visible.findIndex(item => item.id === (stage === 'applying' ? 'done' : stage));
  const interrupted: StageState | null = run.status === 'failed' ? 'failed' : run.status === 'cancelled' ? 'cancelled' : null;

  return visible.map((item, index) => {
    let state: StageState;
    if (finished) state = 'done';
    else if (position === -1) state = 'pending';
    else if (index < position) state = 'done';
    else if (index > position) state = 'pending';
    else if (interrupted) state = interrupted;
    else if (item.id === 'waiting_review') state = 'waiting';
    else state = 'current';
    const label = item.id === 'done' && stage === 'applying' && state === 'current' ? 'Aplicando' : item.label;
    return { id: item.id, label, state };
  });
};

/** Há algo para mostrar em "Resultado"? Evita uma seção vazia enquanto a execução só tem andamento. */
export const hasRunResult = (run: Pick<AiRun, 'summary_pt_br' | 'facts' | 'sources' | 'warnings' | 'model'>): boolean =>
  !!run.summary_pt_br?.trim() || (run.facts?.length ?? 0) > 0 || (run.sources?.length ?? 0) > 0
  || (run.warnings?.length ?? 0) > 0 || run.model?.fallback_used === true;

const STEP_STATUS: Record<string, string> = { started: 'em andamento', succeeded: 'concluída', failed: 'falhou' };
export const stepStatusLabel = (status: string) => STEP_STATUS[status] ?? status;

/** Aviso do servidor pode vir como texto ou como `{code, message}`. */
export const warningText = (warning: string | { code?: string; message?: string }): string | null => {
  if (typeof warning === 'string') return warning.trim() || null;
  return warning?.message?.trim() || null;
};
