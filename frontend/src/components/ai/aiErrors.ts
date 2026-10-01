import type { AiErrorBody } from './aiTypes';

/**
 * Erro da API de IA já traduzido para o que a tela pode mostrar.
 *
 * A tela só exibe `safeMessage` e `traceId` ("código de rastreio"). O erro
 * original do axios (URL, cabeçalhos, corpo, stack) nunca é guardado aqui,
 * justamente para que nenhum componente consiga mostrá-lo por descuido.
 *
 * Fica em arquivo separado do cliente HTTP para que testes e a bancada de
 * prévia possam trocar `aiApi` por um dublê e ainda lançar o mesmo tipo.
 */
export class AiApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly safeMessage: string;
  readonly traceId: string | null;
  /** Status HTTP; 0 quando não houve resposta (rede, timeout). */
  readonly status: number;

  constructor(init: { code: string; retryable: boolean; safeMessage: string; traceId?: string | null; status?: number }) {
    super(init.safeMessage);
    this.name = 'AiApiError';
    this.code = init.code;
    this.retryable = init.retryable;
    this.safeMessage = init.safeMessage;
    this.traceId = init.traceId ?? null;
    this.status = init.status ?? 0;
  }
}

/** Mensagens para quando o servidor não mandou o envelope de erro do contrato. */
const FALLBACK_BY_STATUS: Record<number, { code: string; message: string; retryable: boolean }> = {
  0: { code: 'network_error', message: 'Não foi possível falar com o servidor. Confira a conexão e tente novamente.', retryable: true },
  400: { code: 'invalid_request', message: 'O pedido não pôde ser entendido. Revise o texto e tente novamente.', retryable: false },
  401: { code: 'unauthorized', message: 'Sessão do operador ausente ou expirada.', retryable: false },
  403: { code: 'scope_denied', message: 'Este pedido não está autorizado para o seu usuário.', retryable: false },
  404: { code: 'not_found', message: 'Este item não foi encontrado no seu espaço financeiro.', retryable: false },
  409: { code: 'conflict', message: 'O pedido conflita com uma versão mais recente. Atualize e confira antes de repetir.', retryable: false },
  413: { code: 'payload_too_large', message: 'O pedido ou arquivo excede o tamanho permitido.', retryable: false },
  429: { code: 'rate_limited', message: 'Muitos pedidos em pouco tempo. Tente novamente em instantes.', retryable: true },
  503: { code: 'unavailable', message: 'O operador está indisponível agora. Tente novamente em instantes.', retryable: true },
};
const GENERIC = { code: 'internal_error', message: 'Não foi possível concluir o pedido.', retryable: true };

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object';

/** Lê `{error: {code, retryable, safe_message, trace_id}}` sem confiar na forma. */
export const parseErrorBody = (data: unknown): Partial<AiErrorBody> | null => {
  if (!isRecord(data) || !isRecord(data.error)) return null;
  const body = data.error;
  return {
    code: typeof body.code === 'string' ? body.code : undefined,
    retryable: typeof body.retryable === 'boolean' ? body.retryable : undefined,
    safe_message: typeof body.safe_message === 'string' && body.safe_message.trim() ? body.safe_message : undefined,
    trace_id: typeof body.trace_id === 'string' && body.trace_id ? body.trace_id : undefined,
  };
};

/**
 * Converte qualquer falha em `AiApiError`.
 *
 * Só campos do envelope do contrato chegam à tela. `error.message` do axios
 * ("Request failed with status code 500", "Network Error") é descartado de
 * propósito: é erro técnico cru.
 */
export const toAiApiError = (error: unknown): AiApiError => {
  if (error instanceof AiApiError) return error;
  const response = isRecord(error) && isRecord(error.response) ? error.response : null;
  const status = response && typeof response.status === 'number' ? response.status : 0;
  const body = response ? parseErrorBody(response.data) : null;
  const fallback = FALLBACK_BY_STATUS[status] ?? GENERIC;
  return new AiApiError({
    code: body?.code ?? fallback.code,
    retryable: body?.retryable ?? fallback.retryable,
    safeMessage: body?.safe_message ?? fallback.message,
    traceId: body?.trace_id ?? null,
    status,
  });
};

/** Requisição cancelada por nós (troca de execução, desmontagem). Não é erro para o titular. */
export const isAbort = (error: unknown): boolean => {
  if (!isRecord(error)) return false;
  return error.name === 'AbortError' || error.name === 'CanceledError' || error.code === 'ERR_CANCELED';
};
