import type { AiOperation, AiProposal, AiRun, AiStatus, FinancialSpace, RunStep } from './aiTypes';

/**
 * Dados SINTÉTICOS para os testes e para a bancada de prévia.
 * Nomes, contas, valores e identificadores são inventados; nada veio de extrato
 * real. Este arquivo não é importado pela aplicação, só por testes e pela bancada.
 *
 * As formas de `effect` repetem o que `backend/services/ai/finance/proposals.py`
 * grava: todo efeito traz `items_new`, `items_duplicate` e `totals` (zerados
 * numa baixa), os totais de importação usam `income`/`expense`/`net`/
 * `transfer_skipped`, e a compensação tem `state_after: "revertido"`. Fixture
 * com chave que o backend não emite faria os testes validarem uma tela que não
 * existe em produção.
 */

export const PERSONAL_SPACE: FinancialSpace = { id: 'space-pessoal-0001', name: 'Casa', kind: 'personal' };
export const BUSINESS_SPACE: FinancialSpace = { id: 'space-negocio-0001', name: 'Marketing digital', kind: 'business' };

export const STATUS_READY: AiStatus = {
  enabled: true,
  flags: { cloud: false, email: true, write: true },
  spaces: [PERSONAL_SPACE, BUSINESS_SPACE],
  capabilities: ['finance.read', 'finance.prepare_change', 'finance.apply_change', 'imports.preview'],
  contract_version: '1.1.0',
};

export const STATUS_SINGLE_SPACE: AiStatus = { ...STATUS_READY, spaces: [PERSONAL_SPACE] };

const HASH_A = 'ab'.repeat(32);
const HASH_B = 'cd'.repeat(32);

export const step = (seq: number, label: string, status: RunStep['status'] = 'succeeded', name = 'finance.read'): RunStep => ({
  seq, kind: name.startsWith('model') ? 'inference' : 'tool', name, label, status,
  started_at: '2026-10-01T12:00:00Z', finished_at: status === 'started' ? null : '2026-10-01T12:00:02Z',
});

export const makeRun = (overrides: Partial<AiRun> = {}): AiRun => ({
  run_id: 'run-0001',
  status: 'queued',
  task: 'finance_question',
  contract_version: '1.1.0',
  trace_id: 'rastreio-0001',
  created_at: '2026-10-01T12:00:00Z',
  finished_at: null,
  cancel_requested: false,
  scope: { financial_space: PERSONAL_SPACE, accounts: [{ id: 'conta-0001', name: 'Conta corrente fictícia' }] },
  progress: { stage: null, steps: [] },
  summary_pt_br: null,
  facts: [],
  sources: [],
  proposal_ids: [],
  operation_ids: [],
  warnings: [],
  model: null,
  error: null,
  ...overrides,
});

const OCTOBER = { kind: 'month', start: '2026-10-01', end: '2026-10-31', label: 'outubro/2026' };
const PERSONAL_SCOPE = { financial_space_id: PERSONAL_SPACE.id, kind: 'personal', declared: 'competência mensal' };

/** Pergunta respondida: três valores (um deles ausente) e as fontes de cada um. */
export const QUESTION_DONE: AiRun = makeRun({
  status: 'completed',
  finished_at: '2026-10-01T12:00:05Z',
  progress: {
    stage: 'done',
    steps: [step(1, 'Consultando contas a pagar'), step(2, 'Redigindo a resposta', 'succeeded', 'model.generate')],
  },
  summary_pt_br: 'Em outubro ainda falta pagar R$ 1.250,00. Não encontrei contas vencidas neste período.',
  facts: [
    { key: 'payables.remaining', label: 'Falta pagar', value: '1250.00', unit: 'money', currency: 'BRL', period: OCTOBER, scope: PERSONAL_SCOPE, source_refs: ['sql:payables:2026-10'], as_of: '2026-10-01T12:00:03Z', missing_reason: null, confidence: null },
    { key: 'payables.paid', label: 'Já pago', value: '0.10', unit: 'money', currency: 'BRL', period: OCTOBER, scope: PERSONAL_SCOPE, source_refs: ['sql:payables:2026-10'], as_of: '2026-10-01T12:00:03Z', missing_reason: null, confidence: null },
    { key: 'payables.overdue', label: 'Vencido', value: null, unit: 'money', currency: 'BRL', period: OCTOBER, scope: PERSONAL_SCOPE, source_refs: ['sql:payables:2026-10'], as_of: '2026-10-01T12:00:03Z', missing_reason: 'Nenhuma conta deste período tem vencimento cadastrado.', confidence: null },
    { key: 'payables.count', label: 'Contas em aberto', value: '7', unit: 'count', currency: null, period: OCTOBER, scope: PERSONAL_SCOPE, source_refs: ['sql:payables:2026-10'], as_of: '2026-10-01T12:00:03Z', missing_reason: null, confidence: null },
  ],
  sources: [{ ref: 'sql:payables:2026-10', kind: 'sql', label: 'Contas a pagar de outubro/2026', as_of: '2026-10-01T12:00:03Z', extra: {} }],
  model: { alias: 'local-texto-a', provider: 'ollama', fallback_used: false },
});

/** Baixa parcial: R$ 100,00 de uma conta de R$ 300,00. */
export const PAYMENT_PROPOSAL: AiProposal = {
  proposal_id: 'proposta-0001',
  kind: 'payable_payment',
  status: 'ready',
  version: 3,
  payload_hash: HASH_A,
  requires_review: false,
  expires_at: '2099-10-02T12:00:00Z',
  summary_pt_br: 'Registrar pagamento parcial de R$ 100,00 na conta "Internet fibra".',
  origin: { source_kind: 'manual', label: 'Pedido feito nesta tela', period: { start: '2026-10-01', end: '2026-10-31' } },
  scope: { financial_space: PERSONAL_SPACE, accounts: [{ id: 'conta-0001', name: 'Conta corrente fictícia' }] },
  effect: {
    state_after: 'registrado_pago',
    before: { paid: '0.00', remaining: '300.00', status: 'pending' },
    after: { paid: '100.00', remaining: '200.00', status: 'partial' },
    items_new: 0, items_duplicate: 0, totals: {},
  },
  ambiguities: [],
  evidence: [{ kind: 'manual', ref: 'pedido:run-0001' }],
  operation_id: null,
  run_id: 'run-0001',
};

/** Extrato vindo do e-mail: itens novos, duplicados, uma transferência de fora e duas ambiguidades. */
export const IMPORT_PROPOSAL: AiProposal = {
  proposal_id: 'proposta-0002',
  kind: 'statement_import',
  status: 'ready',
  version: 1,
  payload_hash: HASH_B,
  requires_review: true,
  expires_at: '2099-10-02T12:00:00Z',
  summary_pt_br: 'Extrato de setembro encontrado no e-mail: 42 transações novas e 3 que já existem no aplicativo.',
  origin: { source_kind: 'email', label: 'extrato-setembro-ficticio.ofx', period: { start: '2026-09-01', end: '2026-09-30' } },
  scope: { financial_space: PERSONAL_SPACE, accounts: [{ id: 'conta-0001', name: 'Conta corrente fictícia' }] },
  effect: {
    state_after: 'importado', before: null, after: null,
    items_new: 42, items_duplicate: 3, items_transfer_skipped: 1,
    totals: { income: '5200.00', expense: '4310.75', net: '889.25', transfer_skipped: '500.00' },
  },
  ambiguities: [
    { code: 'transfer_without_destination', message: '1 transferência(s), no total de R$ 500,00, não serão importadas: o extrato não informa a conta de destino.', blocking: false },
    { code: 'uncategorized', message: '4 transações ficaram sem categoria sugerida.', blocking: false },
  ],
  evidence: [
    { kind: 'email', ref: 'email:mensagem-ficticia-0001' },
    { kind: 'ofx_transaction', ref: 'artifact:arquivo-ficticio-0001' },
  ],
  operation_id: null,
  run_id: 'run-0002',
};

export const REVERSAL_PROPOSAL: AiProposal = {
  ...PAYMENT_PROPOSAL,
  proposal_id: 'proposta-0003',
  kind: 'reverse_operation',
  version: 1,
  summary_pt_br: 'Desfazer o pagamento parcial de R$ 100,00 da conta "Internet fibra".',
  origin: { source_kind: 'manual', label: 'Reversão da operação operacao-0001', period: { start: null, end: null } },
  effect: {
    state_after: 'revertido',
    before: { paid: '100.00', remaining: '200.00', status: 'partial' },
    after: { paid: '0.00', remaining: '300.00', status: 'pending' },
    items_new: 0, items_duplicate: 0, totals: {},
  },
  evidence: [{ kind: 'manual', ref: 'operation:operacao-0001' }],
  // Criada por "Desfazer", fora de uma execução: o backend manda `run_id` nulo.
  run_id: null,
};

/** Compensação de uma importação: `items_new` é quantos lançamentos serão cancelados. */
export const IMPORT_REVERSAL_PROPOSAL: AiProposal = {
  ...IMPORT_PROPOSAL,
  proposal_id: 'proposta-0004',
  kind: 'reverse_operation',
  requires_review: false,
  summary_pt_br: 'Reverter a importação do extrato "extrato-setembro-ficticio.ofx": 42 lançamento(s) serão cancelados. O histórico é preservado; nada é apagado.',
  origin: { source_kind: 'manual', label: 'Reversão da operação operacao-0002', period: { start: null, end: null } },
  effect: {
    state_after: 'revertido', before: null, after: null,
    items_new: 42, items_duplicate: 0,
    totals: { income: '5200.00', expense: '4310.75', net: '889.25' },
  },
  ambiguities: [],
  evidence: [{ kind: 'manual', ref: 'operation:operacao-0002' }],
  run_id: null,
};

export const PAYMENT_OPERATION: AiOperation = {
  operation_id: 'operacao-0001',
  kind: 'payable_payment',
  status: 'applied',
  proposal_id: PAYMENT_PROPOSAL.proposal_id,
  run_id: 'run-0003',
  trace_id: 'rastreio-0003',
  applied_at: '2026-10-01T12:05:00Z',
  reversed_at: null,
  reversed_by_operation_id: null,
  summary_pt_br: 'Pagamento parcial de R$ 100,00 registrado na conta "Internet fibra".',
  scope: PAYMENT_PROPOSAL.scope,
  effect: PAYMENT_PROPOSAL.effect,
};

/** Execução criada pela aprovação: já aplicou e aponta para a operação gravada. */
export const APPLIED_RUN: AiRun = makeRun({
  run_id: 'run-0003',
  task: 'apply_proposal',
  status: 'completed',
  trace_id: 'rastreio-0003',
  finished_at: '2026-10-01T12:05:01Z',
  progress: { stage: 'done', steps: [step(1, 'Gravando o pagamento', 'succeeded', 'finance.apply_change')] },
  summary_pt_br: 'Pagamento registrado.',
  proposal_ids: [PAYMENT_PROPOSAL.proposal_id],
  operation_ids: [PAYMENT_OPERATION.operation_id],
});
