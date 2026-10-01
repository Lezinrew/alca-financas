// @vitest-environment node
/**
 * Cliente HTTP testado contra um servidor HTTP REAL, local e descartável.
 * O que vai no fio (cabeçalhos, corpo, URL) é o que o backend receberia.
 * Ambiente node: sem jsdom, o axios usa o adaptador http e não há CORS no caminho.
 */
import { Buffer } from 'node:buffer';
import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AiApiError as AiApiErrorType } from './aiErrors';

// Se o cliente da IA passasse a usar a instância `api` do aplicativo, o
// interceptor de lá consultaria a sessão Supabase e, em 401, faria signOut.
const supabaseAuth = vi.hoisted(() => ({
  getSession: vi.fn(async () => ({ data: { session: null } })),
  refreshSession: vi.fn(async () => ({ data: { session: null }, error: null })),
  signOut: vi.fn(async () => ({ error: null })),
}));
vi.mock('../../utils/supabaseClient', () => ({ supabase: { auth: supabaseAuth } }));

interface Seen { method: string; url: string; headers: http.IncomingHttpHeaders; body: string }
type Reply = { status: number; body: unknown; contentType?: string };

let server: http.Server;
let baseUrl = '';
let seen: Seen[] = [];
let reply: (request: Seen) => Reply = () => ({ status: 200, body: {} });

// Cada teste recarrega o módulo do cliente; a folga evita falso negativo por lentidão da máquina.
vi.setConfig({ testTimeout: 30_000 });

beforeAll(async () => {
  server = http.createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on('data', chunk => chunks.push(chunk as Buffer));
    request.on('end', () => {
      const record: Seen = { method: request.method ?? '', url: request.url ?? '', headers: request.headers, body: Buffer.concat(chunks).toString('utf8') };
      seen.push(record);
      const { status, body, contentType } = reply(record);
      response.writeHead(status, { 'Content-Type': contentType ?? 'application/json' });
      response.end(typeof body === 'string' ? body : JSON.stringify(body));
    });
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  // Primeira carga do axios é lenta em máquina ocupada; fazê-la aqui tira esse custo do primeiro teste.
  await import('./aiApi');
}, 60_000);
afterAll(async () => {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
});

/**
 * Carrega o cliente do zero apontando para o servidor de teste. `baseURL` e o
 * cookie são lidos na carga do módulo e a cada requisição, por isso o módulo é
 * reimportado. As classes de erro vêm da MESMA carga, senão `instanceof` falha.
 */
const loadClient = async (cookie: string, apiUrl = baseUrl) => {
  vi.resetModules();
  vi.stubEnv('VITE_API_URL', apiUrl);
  vi.stubGlobal('document', { cookie });
  const client = await import('./aiApi');
  const errors = await import('./aiErrors');
  return { ...client, ...errors };
};

beforeEach(() => { seen = []; reply = () => ({ status: 200, body: {} }); vi.clearAllMocks(); });
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

const errorEnvelope = (code: string, safe_message: string, trace_id: string, retryable = false) => ({ error: { code, retryable, safe_message, trace_id } });

describe('aiApi contra servidor HTTP local', () => {
  it('createRun envia corpo, Idempotency-Key e o token CSRF lido do cookie', async () => {
    const { aiApi } = await loadClient('tema=escuro; alcahub_csrf=csrf-de-teste; outro=1');
    reply = () => ({ status: 202, body: { run_id: 'run-0001', status: 'queued', trace_id: 'rastreio-0001' } });
    const payload = { task: 'finance_question', message: 'Quanto falta pagar em outubro?', financial_space_id: 'space-pessoal-0001', privacy: 'local_only', input_refs: [] } as const;

    const accepted = await aiApi.createRun({ ...payload, input_refs: [] }, { idempotencyKey: 'chave-de-envio-0001' });

    expect(accepted).toEqual({ run_id: 'run-0001', status: 'queued', trace_id: 'rastreio-0001' });
    expect(seen).toHaveLength(1);
    expect(seen[0].method).toBe('POST');
    expect(seen[0].url).toBe('/api/ai/v1/runs');
    expect(seen[0].headers['idempotency-key']).toBe('chave-de-envio-0001');
    expect(seen[0].headers['x-csrf-token']).toBe('csrf-de-teste');
    expect(JSON.parse(seen[0].body)).toEqual(payload);
  });

  it('usa o cookie com prefixo __Host- quando o backend roda com cookie seguro', async () => {
    const { aiApi } = await loadClient('__Host-alcahub_csrf=csrf-seguro-de-teste');
    await aiApi.cancelRun('run-0001');
    expect(seen[0].method).toBe('POST');
    expect(seen[0].url).toBe('/api/ai/v1/runs/run-0001/cancel');
    expect(seen[0].headers['x-csrf-token']).toBe('csrf-seguro-de-teste');
  });

  it('todo POST leva CSRF; GET não precisa', async () => {
    const { aiApi } = await loadClient('alcahub_csrf=csrf-de-teste');
    reply = request => {
      if (request.url.endsWith('/approve')) return { status: 202, body: { run_id: 'run-0003', status: 'queued', trace_id: 'rastreio-0003' } };
      if (request.url.endsWith('/reverse')) return { status: 201, body: { proposal_id: 'proposta-0003' } };
      if (request.url.includes('/runs/')) return { status: 200, body: { run_id: 'run-0001', status: 'running', task: 'finance_question', trace_id: 'rastreio-0001' } };
      return { status: 200, body: {} };
    };

    await aiApi.approveProposal('proposta-0001', { payload_hash: 'ab'.repeat(32), version: 3 });
    await aiApi.rejectProposal('proposta-0001', 'Valor errado');
    await aiApi.reverseOperation('operacao-0001', 'Lançado na conta errada');
    await aiApi.getRun('run-0001');

    const [approve, reject, reverse, get] = seen;
    expect(approve.url).toBe('/api/ai/v1/proposals/proposta-0001/approve');
    expect(JSON.parse(approve.body)).toEqual({ payload_hash: 'ab'.repeat(32), version: 3 });
    expect(reject.url).toBe('/api/ai/v1/proposals/proposta-0001/reject');
    expect(JSON.parse(reject.body)).toEqual({ reason: 'Valor errado' });
    expect(reverse.url).toBe('/api/ai/v1/operations/operacao-0001/reverse');
    expect(JSON.parse(reverse.body)).toEqual({ reason: 'Lançado na conta errada' });
    for (const post of [approve, reject, reverse]) expect(post.headers['x-csrf-token']).toBe('csrf-de-teste');
    expect(get.method).toBe('GET');
    expect(get.headers['x-csrf-token']).toBeUndefined();
  });

  it('aprovação aceita a resposta da spec e também a visão da proposta, sem tratar sucesso como falha', async () => {
    const { aiApi, AiApiError } = await loadClient('alcahub_csrf=csrf-de-teste');
    const approve = () => aiApi.approveProposal('proposta-0001', { payload_hash: 'ab'.repeat(32), version: 3 });

    // Spec: 202 com o run_id da execução que aplica.
    reply = () => ({ status: 202, body: { run_id: 'run-0003', status: 'queued', trace_id: 'rastreio-0003' } });
    await expect(approve()).resolves.toEqual({ run_id: 'run-0003', status: 'queued', trace_id: 'rastreio-0003' });

    // Serviço de propostas: a visão da proposta, com o run_id da execução de origem...
    reply = () => ({ status: 200, body: { proposal_id: 'proposta-0001', status: 'approved', version: 3, run_id: 'run-0001' } });
    await expect(approve()).resolves.toEqual({ run_id: 'run-0001', status: 'approved', trace_id: null });
    // ...ou sem execução (compensação criada por "Desfazer"). A aprovação FOI registrada.
    reply = () => ({ status: 200, body: { proposal_id: 'proposta-0003', status: 'approved', version: 1, run_id: null } });
    await expect(approve()).resolves.toEqual({ run_id: null, status: 'approved', trace_id: null });

    // O que não é um objeto do contrato continua sendo falha, nunca "aprovado".
    for (const body of ['<!doctype html><html><body>app</body></html>', {}, { run_id: '' }, []]) {
      reply = () => ({ status: 200, body, contentType: typeof body === 'string' ? 'text/html' : undefined });
      const failure = await approve().catch((error: unknown) => error);
      expect(failure).toBeInstanceOf(AiApiError);
      expect(failure).toMatchObject({ code: 'invalid_response' });
    }
  });

  it('listRuns manda o espaço e o limite na query', async () => {
    const { aiApi } = await loadClient('');
    reply = () => ({ status: 200, body: { runs: [{ run_id: 'run-0001', status: 'completed', task: 'finance_question' }], next_cursor: null } });
    const list = await aiApi.listRuns({ financial_space_id: 'space-pessoal-0001', limit: 5 });
    expect(seen[0].url).toBe('/api/ai/v1/runs?financial_space_id=space-pessoal-0001&limit=5');
    expect(list.runs.map(run => run.run_id)).toEqual(['run-0001']);
  });

  it('erro do contrato vira AiApiError com safe_message e código de rastreio', async () => {
    const { aiApi, AiApiError } = await loadClient('alcahub_csrf=csrf-de-teste');
    reply = () => ({ status: 409, body: errorEnvelope('stale_proposal', 'A proposta ficou desatualizada. Gere uma nova prévia.', 'rastreio-0409') });

    const failure = await aiApi.approveProposal('proposta-0001', { payload_hash: 'ab'.repeat(32), version: 3 }).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(AiApiError);
    expect(failure).toMatchObject({ code: 'stale_proposal', retryable: false, status: 409, traceId: 'rastreio-0409', safeMessage: 'A proposta ficou desatualizada. Gere uma nova prévia.' });
  });

  it('corpo técnico do servidor nunca chega à mensagem exibida', async () => {
    const { aiApi, AiApiError } = await loadClient('');
    reply = () => ({ status: 500, contentType: 'text/html', body: '<html>Traceback (most recent call last): psycopg2.OperationalError senha=segredo</html>' });

    const failure = await aiApi.getRun('run-0001').catch((error: unknown) => error) as AiApiErrorType;

    expect(failure).toBeInstanceOf(AiApiError);
    expect(failure.status).toBe(500);
    expect(failure.safeMessage).toBe('Não foi possível concluir o pedido.');
    expect(JSON.stringify({ ...failure, message: failure.message })).not.toMatch(/Traceback|psycopg2|segredo|status code/);
  });

  it('401, 403 e 503 viram erro tratável e não tocam na sessão do aplicativo', async () => {
    const { aiApi, AiApiError } = await loadClient('');
    const outcomes: AiApiErrorType[] = [];
    for (const [status, code] of [[401, 'unauthorized'], [403, 'capability_denied'], [503, 'ai_disabled']] as const) {
      reply = () => ({ status, body: errorEnvelope(code, 'Mensagem segura do servidor.', `rastreio-0${status}`) });
      outcomes.push(await aiApi.getStatus().catch((error: unknown) => error) as AiApiErrorType);
    }

    expect(outcomes.map(error => [error.status, error.code])).toEqual([[401, 'unauthorized'], [403, 'capability_denied'], [503, 'ai_disabled']]);
    for (const error of outcomes) expect(error).toBeInstanceOf(AiApiError);
    // Cada chamada foi feita uma única vez: nada de refresh de sessão e nova tentativa.
    expect(seen).toHaveLength(3);
    expect(supabaseAuth.getSession).not.toHaveBeenCalled();
    expect(supabaseAuth.refreshSession).not.toHaveBeenCalled();
    expect(supabaseAuth.signOut).not.toHaveBeenCalled();
    for (const request of seen) expect(request.headers.authorization).toBeUndefined();
  });

  it('401 sem envelope ainda recebe uma explicação em português', async () => {
    const { aiApi } = await loadClient('');
    reply = () => ({ status: 401, body: {} });
    const failure = await aiApi.getStatus().catch((error: unknown) => error) as AiApiErrorType;
    expect(failure).toMatchObject({ status: 401, code: 'unauthorized', traceId: null });
    expect(failure.safeMessage).toMatch(/Sessão do operador/);
  });

  it('resposta 200 com forma inesperada é falha, não "vazio"', async () => {
    const { aiApi, AiApiError } = await loadClient('');
    // Um proxy sem a rota pode devolver o index.html do aplicativo com status 200.
    reply = () => ({ status: 200, contentType: 'text/html', body: '<!doctype html><html><body>app</body></html>' });

    for (const request of [() => aiApi.getStatus(), () => aiApi.listRuns(), () => aiApi.getRun('run-0001'), () => aiApi.getProposal('proposta-0001')]) {
      const failure = await request().catch((error: unknown) => error);
      expect(failure).toBeInstanceOf(AiApiError);
      expect(failure).toMatchObject({ code: 'invalid_response' });
    }
  });

  it('servidor fora do ar vira erro de rede repetível, sem detalhe técnico', async () => {
    // Porta que acabou de ser liberada: a conexão é recusada na hora.
    const closed = http.createServer();
    await new Promise<void>(resolve => closed.listen(0, '127.0.0.1', resolve));
    const deadUrl = `http://127.0.0.1:${(closed.address() as AddressInfo).port}`;
    await new Promise(resolve => closed.close(resolve));
    const { aiApi, AiApiError } = await loadClient('', deadUrl);
    const failure = await aiApi.getStatus().catch((error: unknown) => error) as AiApiErrorType;
    expect(failure).toBeInstanceOf(AiApiError);
    expect(failure).toMatchObject({ status: 0, code: 'network_error', retryable: true });
    expect(failure.safeMessage).not.toMatch(/ECONNREFUSED|127\.0\.0\.1|Network Error/);
  });

  it('AbortSignal cancela a requisição e não é tratado como erro do servidor', async () => {
    const { aiApi, AiApiError, isAbort } = await loadClient('');
    const controller = new AbortController();
    controller.abort();
    const failure = await aiApi.getRun('run-0001', { signal: controller.signal }).catch((error: unknown) => error);
    expect(isAbort(failure)).toBe(true);
    expect(failure).not.toBeInstanceOf(AiApiError);
    expect(seen).toHaveLength(0);
  });

  it('getStatus normaliza flags: só o que o servidor afirmou vira true ou false', async () => {
    const { aiApi } = await loadClient('');
    reply = () => ({ status: 200, body: { enabled: true, flags: { email: false, write_enabled: true }, spaces: [{ id: 'space-pessoal-0001', name: 'Casa', kind: 'personal' }, { nome: 'sem id' }], capabilities: ['finance.read', 7] } });
    const status = await aiApi.getStatus();
    expect(status).toEqual({
      enabled: true,
      flags: { cloud: null, email: false, write: true },
      spaces: [{ id: 'space-pessoal-0001', name: 'Casa', kind: 'personal' }],
      capabilities: ['finance.read'],
      contract_version: null,
    });
  });

  it('IA desligada chega como status 200 com enabled false', async () => {
    const { aiApi } = await loadClient('');
    reply = () => ({ status: 200, body: { enabled: false } });
    await expect(aiApi.getStatus()).resolves.toMatchObject({ enabled: false, spaces: [] });
  });
});

describe('configuração do cliente', () => {
  it('usa a mesma origem por padrão e o host de VITE_API_URL quando absoluto', async () => {
    const { resolveAiBaseUrl } = await loadClient('');
    expect(resolveAiBaseUrl(undefined)).toBe('/api/ai/v1');
    expect(resolveAiBaseUrl('/api')).toBe('/api/ai/v1');
    expect(resolveAiBaseUrl('https://api.exemplo.test')).toBe('https://api.exemplo.test/api/ai/v1');
    expect(resolveAiBaseUrl('https://api.exemplo.test/api/')).toBe('https://api.exemplo.test/api/ai/v1');
  });

  it('envia cookies da sessão do backend novo e não tem interceptor de resposta', async () => {
    const { aiHttp } = await loadClient('');
    expect(aiHttp.defaults.withCredentials).toBe(true);
    // Nenhum interceptor de resposta: não existe caminho que deslogue ou redirecione.
    const { handlers } = aiHttp.interceptors.response as unknown as { handlers: unknown[] };
    expect(handlers.filter(Boolean)).toHaveLength(0);
  });

  it('readCsrfToken prefere o cookie seguro e ignora cookie vazio', async () => {
    const { readCsrfToken } = await loadClient('');
    expect(readCsrfToken('alcahub_csrf=simples; __Host-alcahub_csrf=seguro')).toBe('seguro');
    expect(readCsrfToken('alcahub_csrf=valor%20com%20espaco')).toBe('valor com espaco');
    expect(readCsrfToken('alcahub_csrf=; outro=1')).toBeNull();
    expect(readCsrfToken('xalcahub_csrf=intruso')).toBeNull();
  });
});
