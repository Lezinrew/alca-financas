import axios from 'axios';
import { AiApiError, isAbort, toAiApiError } from './aiErrors';
import type {
  AiOperation, AiProposal, AiRun, AiRunSummary, AiStatus, ApprovalAccepted, CreateRunPayload, FinancialSpace,
  RequestOptions, ReversalCreated, RunAccepted, RunList,
} from './aiTypes';

/**
 * Cliente HTTP da plataforma de IA (`/api/ai/v1`).
 *
 * Por que uma instância axios própria, e não a `api` de `utils/api.ts`:
 * o interceptor de lá trata qualquer 401 como sessão Supabase vencida, faz
 * `signOut` e manda para `/login`. A IA usa outra sessão (cookie do backend
 * novo). Se ela responder 401, o titular continua logado no aplicativo; só o
 * operador fica indisponível. Aqui nenhum status desloga nem redireciona:
 * todo erro vira `AiApiError` e a tela decide o que explicar.
 */

const trimTrailingSlashes = (value: string) => value.replace(/\/+$/, '');

/** Mesmo host da API do aplicativo: `VITE_API_URL` absoluta ou a própria origem (proxy). */
export const resolveAiBaseUrl = (value?: string): string => {
  const trimmed = trimTrailingSlashes((value ?? '').trim());
  const host = /^https?:\/\//i.test(trimmed)
    ? (trimmed.toLowerCase().endsWith('/api') ? trimmed.slice(0, -4) : trimmed)
    : '';
  return `${host}/api/ai/v1`;
};

/** Com cookie seguro o backend usa o prefixo `__Host-`; em desenvolvimento, o nome simples. */
export const CSRF_COOKIE_NAMES = ['__Host-alcahub_csrf', 'alcahub_csrf'] as const;

export const readCsrfToken = (cookieHeader?: string): string | null => {
  const source = cookieHeader ?? (typeof document === 'undefined' ? '' : document.cookie);
  const pairs = source.split(';').map(part => part.trim());
  for (const name of CSRF_COOKIE_NAMES) {
    const hit = pairs.find(pair => pair.startsWith(`${name}=`));
    if (!hit) continue;
    const raw = hit.slice(name.length + 1);
    if (!raw) continue;
    try { return decodeURIComponent(raw); } catch { return raw; }
  }
  return null;
};

export const aiHttp = axios.create({
  baseURL: resolveAiBaseUrl(import.meta.env.VITE_API_URL),
  // A sessão do backend novo vive em cookie HttpOnly; sem isto ele não é enviado
  // quando a API está em outra origem.
  withCredentials: true,
  timeout: 30_000,
  headers: { Accept: 'application/json' },
});

// O backend exige o token CSRF em todo POST. Lemos o cookie a cada requisição
// porque o token pode ser rotacionado durante a sessão.
aiHttp.interceptors.request.use(config => {
  if ((config.method ?? 'get').toLowerCase() === 'post') {
    const token = readCsrfToken();
    if (token) config.headers.set('X-CSRF-Token', token);
  }
  return config;
});

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const stringList = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];

/**
 * Resposta com forma inesperada é FALHA, nunca "vazio".
 *
 * Caso real que isto protege: sem a rota no backend, um proxy pode devolver o
 * `index.html` com status 200. Tratar isso como "sem execuções" ou "valor zero"
 * mentiria para o titular.
 */
const unexpected = () => new AiApiError({
  code: 'invalid_response', retryable: true, status: 0,
  safeMessage: 'O servidor devolveu uma resposta inesperada. Tente novamente em instantes.',
});

const requireRecord = (data: unknown, idField: string): Record<string, unknown> => {
  if (!isRecord(data) || typeof data[idField] !== 'string' || !data[idField]) throw unexpected();
  return data;
};

const normalizeSpaces = (value: unknown): FinancialSpace[] => (Array.isArray(value) ? value : [])
  .filter(isRecord)
  .filter(space => typeof space.id === 'string' && space.id)
  .map(space => ({
    id: space.id as string,
    name: typeof space.name === 'string' && space.name.trim() ? space.name : 'Espaço sem nome',
    kind: typeof space.kind === 'string' ? space.kind : 'personal',
  }));

export const normalizeStatus = (data: unknown): AiStatus => {
  if (!isRecord(data) || typeof data.enabled !== 'boolean') throw unexpected();
  const flags = isRecord(data.flags) ? data.flags : {};
  // Três valores: ligada, desligada ou não informada (`null`). A tela só bloqueia
  // uma ação quando o servidor disse explicitamente que está desligada; no caso
  // "não informada" quem decide é o servidor, que responde com o erro adequado.
  const flag = (name: string): boolean | null => {
    for (const value of [flags[name], flags[`${name}_enabled`], data[`${name}_enabled`]]) {
      if (typeof value === 'boolean') return value;
    }
    return null;
  };
  return {
    enabled: data.enabled,
    flags: { cloud: flag('cloud'), email: flag('email'), write: flag('write') },
    spaces: normalizeSpaces(data.spaces ?? data.financial_spaces),
    capabilities: stringList(data.capabilities),
    contract_version: typeof data.contract_version === 'string' ? data.contract_version : null,
  };
};

export const normalizeRunList = (data: unknown): RunList => {
  if (!isRecord(data)) throw unexpected();
  const list = data.runs ?? data.items;
  if (!Array.isArray(list)) throw unexpected();
  return {
    runs: list.filter(isRecord).filter(run => typeof run.run_id === 'string') as unknown as AiRunSummary[],
    next_cursor: typeof data.next_cursor === 'string' ? data.next_cursor : null,
  };
};

/**
 * A aprovação já foi REGISTRADA quando o servidor responde 2xx. Por isso a
 * leitura da resposta é tolerante: aceita `{run_id, ...}` (spec) e também a
 * visão da proposta (`{proposal_id, run_id: <origem> | null, ...}`), que é o
 * que o serviço de propostas devolve. Exigir `run_id` aqui mostraria "resposta
 * inesperada" para uma aprovação que deu certo, e o titular tentaria de novo.
 * Só o que não é um objeto do contrato (ex.: o index.html de um proxy) é falha.
 */
export const normalizeApproval = (data: unknown): ApprovalAccepted => {
  if (!isRecord(data)) throw unexpected();
  const runId = typeof data.run_id === 'string' && data.run_id ? data.run_id : null;
  if (!runId && (typeof data.proposal_id !== 'string' || !data.proposal_id)) throw unexpected();
  return {
    run_id: runId,
    status: typeof data.status === 'string' ? data.status : null,
    trace_id: typeof data.trace_id === 'string' ? data.trace_id : null,
  };
};

const call = async <T>(request: () => Promise<{ data: unknown }>, parse: (data: unknown) => T): Promise<T> => {
  try {
    const { data } = await request();
    return parse(data);
  } catch (error) {
    // Cancelamento é nosso (troca de execução, desmontagem): quem chamou decide ignorar.
    if (isAbort(error)) throw error;
    throw toAiApiError(error);
  }
};

const id = (value: string) => encodeURIComponent(value);

export const aiApi = {
  getStatus: (options: RequestOptions = {}): Promise<AiStatus> =>
    call(() => aiHttp.get('/status', { signal: options.signal }), normalizeStatus),

  createRun: (payload: CreateRunPayload, options: RequestOptions & { idempotencyKey: string }): Promise<RunAccepted> =>
    call(
      () => aiHttp.post('/runs', payload, { signal: options.signal, headers: { 'Idempotency-Key': options.idempotencyKey } }),
      data => requireRecord(data, 'run_id') as unknown as RunAccepted,
    ),

  getRun: (runId: string, options: RequestOptions = {}): Promise<AiRun> =>
    call(() => aiHttp.get(`/runs/${id(runId)}`, { signal: options.signal }), data => requireRecord(data, 'run_id') as unknown as AiRun),

  listRuns: (params: { financial_space_id?: string; limit?: number; cursor?: string } = {}, options: RequestOptions = {}): Promise<RunList> =>
    call(() => aiHttp.get('/runs', { params, signal: options.signal }), normalizeRunList),

  cancelRun: (runId: string, options: RequestOptions = {}): Promise<void> =>
    call(() => aiHttp.post(`/runs/${id(runId)}/cancel`, {}, { signal: options.signal }), () => undefined),

  getProposal: (proposalId: string, options: RequestOptions = {}): Promise<AiProposal> =>
    call(() => aiHttp.get(`/proposals/${id(proposalId)}`, { signal: options.signal }), data => requireRecord(data, 'proposal_id') as unknown as AiProposal),

  /**
   * A aprovação vale para UM conteúdo e UMA versão: o servidor recusa
   * (`stale_proposal`) se a proposta mudou depois que o titular a leu.
   */
  approveProposal: (proposalId: string, approval: { payload_hash: string; version: number }, options: RequestOptions = {}): Promise<ApprovalAccepted> =>
    call(
      () => aiHttp.post(`/proposals/${id(proposalId)}/approve`, { payload_hash: approval.payload_hash, version: approval.version }, { signal: options.signal }),
      normalizeApproval,
    ),

  rejectProposal: (proposalId: string, reason: string, options: RequestOptions = {}): Promise<void> =>
    call(() => aiHttp.post(`/proposals/${id(proposalId)}/reject`, { reason }, { signal: options.signal }), () => undefined),

  getOperation: (operationId: string, options: RequestOptions = {}): Promise<AiOperation> =>
    call(() => aiHttp.get(`/operations/${id(operationId)}`, { signal: options.signal }), data => requireRecord(data, 'operation_id') as unknown as AiOperation),

  /** Desfazer não apaga nada: cria uma proposta de compensação, que também precisa de aprovação. */
  reverseOperation: (operationId: string, reason: string, options: RequestOptions = {}): Promise<ReversalCreated> =>
    call(
      () => aiHttp.post(`/operations/${id(operationId)}/reverse`, { reason }, { signal: options.signal }),
      data => requireRecord(data, 'proposal_id') as unknown as ReversalCreated,
    ),
};

export type AiApi = typeof aiApi;
