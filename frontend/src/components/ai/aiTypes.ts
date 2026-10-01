/**
 * Tipos da API `/api/ai/v1` (spec de implementação, seção 4).
 *
 * Dinheiro chega como string decimal ("1250.00") e continua string até a
 * formatação: converter para `number` perderia centavos em valores grandes e
 * abriria espaço para o erro clássico `Number(x) || 0`, que transforma ausência
 * em zero. Ausência de dado é `value: null` com `missing_reason`.
 */

export type SpaceKind = 'personal' | 'family' | 'business' | (string & {});

export interface FinancialSpace {
  id: string;
  name: string;
  kind: SpaceKind;
}

export interface AccountRef {
  id: string;
  name: string;
}

/** `null` = o servidor não informou a flag; só `false` bloqueia algo na tela. */
export interface AiFlags {
  cloud: boolean | null;
  email: boolean | null;
  write: boolean | null;
}

export interface AiStatus {
  enabled: boolean;
  flags: AiFlags;
  spaces: FinancialSpace[];
  capabilities: string[];
  contract_version: string | null;
}

/** Tarefas que o titular pode pedir. As demais são criadas só pelo servidor. */
export type RequestableTask = 'finance_question' | 'statement_import';
export type RunTask = RequestableTask | 'apply_proposal' | 'reverse_operation' | (string & {});

export type RunStatus =
  | 'queued' | 'running' | 'waiting_review' | 'completed'
  | 'failed' | 'cancelled' | 'needs_reconciliation';

export type ProgressStage = 'searching' | 'reading' | 'preparing' | 'waiting_review' | 'applying' | 'done';

export interface RunStep {
  seq: number;
  kind: 'tool' | 'inference' | (string & {});
  name: string;
  label: string;
  status: 'started' | 'succeeded' | 'failed' | (string & {});
  started_at?: string | null;
  finished_at?: string | null;
}

export interface AiErrorBody {
  code: string;
  retryable: boolean;
  safe_message: string;
  trace_id: string | null;
}

export interface FactPeriod {
  kind?: string;
  start?: string | null;
  end?: string | null;
  label?: string | null;
}

export interface FactScope {
  financial_space_id?: string;
  kind?: SpaceKind;
  declared?: string | null;
}

export interface Fact {
  key: string;
  label: string;
  /** Decimal em string; `null` significa "sem dado" (nunca zero). */
  value: string | null;
  unit: 'money' | 'count' | 'text' | 'date' | (string & {});
  currency?: string | null;
  period?: FactPeriod | null;
  scope?: FactScope | null;
  source_refs: string[];
  as_of?: string | null;
  missing_reason?: string | null;
  confidence?: number | null;
}

export interface Source {
  ref: string;
  kind: string;
  label: string;
  as_of?: string | null;
  extra?: Record<string, unknown>;
}

export interface RunScope {
  financial_space?: FinancialSpace | null;
  accounts?: AccountRef[];
}

export interface RunModel {
  alias?: string | null;
  provider?: string | null;
  fallback_used?: boolean;
}

export interface AiRun {
  run_id: string;
  status: RunStatus;
  task: RunTask;
  contract_version?: string | null;
  trace_id: string | null;
  created_at?: string | null;
  finished_at?: string | null;
  cancel_requested?: boolean;
  scope?: RunScope | null;
  progress?: { stage?: ProgressStage | null; steps?: RunStep[] } | null;
  summary_pt_br?: string | null;
  facts?: Fact[];
  sources?: Source[];
  proposal_ids?: string[];
  operation_ids?: string[];
  warnings?: Array<string | { code?: string; message?: string }>;
  model?: RunModel | null;
  error?: AiErrorBody | null;
}

/** Item do histórico: o mesmo recurso, mas a lista pode vir resumida. */
export type AiRunSummary = Pick<AiRun, 'run_id' | 'status' | 'task'> & Partial<AiRun>;

export interface RunList {
  runs: AiRunSummary[];
  next_cursor: string | null;
}

export interface CreateRunPayload {
  task: RequestableTask;
  message: string;
  financial_space_id?: string;
  privacy: 'local_only';
  input_refs: string[];
}

export interface RunAccepted {
  run_id: string;
  status: RunStatus;
  trace_id: string | null;
}

/**
 * Resposta de `POST /proposals/{id}/approve`.
 *
 * A spec diz `202` com o `run_id` da execução que aplica a proposta. O serviço
 * de propostas, porém, devolve a visão da proposta, cujo `run_id` é o da
 * execução de ORIGEM (ou nulo, numa compensação criada por "Desfazer"). A tela
 * aceita as duas formas: `run_id` nulo ou igual ao da execução aberta significa
 * "reconsulte o que já está na tela", nunca "abra outra execução".
 */
export interface ApprovalAccepted {
  run_id: string | null;
  status?: string | null;
  trace_id?: string | null;
}

export type ProposalKind = 'payable_payment' | 'statement_import' | 'reverse_operation' | (string & {});
export type ProposalStatus = 'draft' | 'ready' | 'approved' | 'applied' | 'rejected' | 'expired' | 'stale';

/**
 * Estado que o registro terá depois do efeito. Os três primeiros nunca podem
 * ser confundidos na tela (contrato, seção 12). `revertido` é o estado depois
 * de uma compensação ("Desfazer").
 */
export type LedgerState = 'conferido' | 'registrado_pago' | 'conciliado' | 'importado' | 'revertido' | (string & {});

export interface EffectSnapshot {
  paid?: string | null;
  remaining?: string | null;
  status?: string | null;
}

export interface ProposalEffect {
  state_after?: LedgerState | null;
  before?: EffectSnapshot | null;
  after?: EffectSnapshot | null;
  items_new?: number | null;
  items_duplicate?: number | null;
  /** Transferências do extrato que ficam de fora (o OFX não informa a conta de destino). */
  items_transfer_skipped?: number | null;
  /**
   * Totais em string decimal. Chaves emitidas pelo backend: `income`, `expense`,
   * `net` e `transfer_skipped`. Baixa e compensação de baixa mandam `{}`.
   */
  totals?: Record<string, unknown> | null;
}

export interface AiProposal {
  proposal_id: string;
  kind: ProposalKind;
  status: ProposalStatus;
  version: number;
  payload_hash: string;
  requires_review?: boolean;
  expires_at?: string | null;
  summary_pt_br?: string | null;
  origin?: {
    source_kind?: string | null;
    label?: string | null;
    period?: { start?: string | null; end?: string | null } | null;
  } | null;
  scope?: RunScope | null;
  effect?: ProposalEffect | null;
  /** `blocking: true` impede a aprovação: a proposta fica em `draft` até uma nova prévia. */
  ambiguities?: Array<{ code?: string; message: string; blocking?: boolean }>;
  evidence?: Array<{ kind?: string; ref: string; label?: string | null }>;
  operation_id?: string | null;
  run_id?: string | null;
}

export interface AiOperation {
  operation_id: string;
  kind?: ProposalKind | null;
  status: 'applied' | 'reversed' | (string & {});
  proposal_id?: string | null;
  run_id?: string | null;
  trace_id?: string | null;
  applied_at?: string | null;
  reversed_at?: string | null;
  reversed_by_operation_id?: string | null;
  summary_pt_br?: string | null;
  scope?: RunScope | null;
  effect?: ProposalEffect | null;
}

export interface ReversalCreated {
  proposal_id: string;
}

export interface RequestOptions {
  signal?: AbortSignal;
}
