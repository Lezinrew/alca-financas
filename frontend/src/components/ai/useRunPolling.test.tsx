import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { aiApi } from './aiApi';
import { AiApiError } from './aiErrors';
import { makeRun, step } from './fixtures';
import type { AiRun } from './aiTypes';
import { DEFAULT_POLL_SCHEDULE, MAX_CONSECUTIVE_FAILURES, shouldKeepPolling, useRunPolling } from './useRunPolling';

// Dublê só da fronteira de rede; o relógio é falso para medir os intervalos de verdade.
vi.mock('./aiApi', () => ({ aiApi: { getRun: vi.fn() } }));

const getRun = () => vi.mocked(aiApi.getRun);
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const running = (overrides: Partial<AiRun> = {}) => makeRun({ status: 'running', progress: { stage: 'searching', steps: [] }, ...overrides });
const transient = () => new AiApiError({ code: 'model_unavailable', retryable: true, safeMessage: 'Nenhum modelo autorizado está disponível agora.', traceId: 'rastreio-0503', status: 503 });

beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers(); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('useRunPolling', () => {
  it('consulta com intervalo crescente enquanto nada muda', async () => {
    getRun().mockResolvedValue(running());
    renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    expect(getRun()).toHaveBeenCalledTimes(1);

    // 1000, 1500, 2500, 4000 ms: cada espera é maior que a anterior.
    let calls = 1;
    for (const delay of DEFAULT_POLL_SCHEDULE.slice(0, 4)) {
      await advance(delay - 1);
      expect(getRun()).toHaveBeenCalledTimes(calls);
      await advance(1);
      calls += 1;
      expect(getRun()).toHaveBeenCalledTimes(calls);
    }
    expect([...DEFAULT_POLL_SCHEDULE]).toEqual([...DEFAULT_POLL_SCHEDULE].sort((a, b) => a - b));
    expect(new Set(DEFAULT_POLL_SCHEDULE).size).toBe(DEFAULT_POLL_SCHEDULE.length);
  });

  it('volta ao intervalo curto quando o servidor relata progresso', async () => {
    getRun().mockResolvedValue(running());
    renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    await advance(DEFAULT_POLL_SCHEDULE[0]);
    await advance(DEFAULT_POLL_SCHEDULE[1]);
    expect(getRun()).toHaveBeenCalledTimes(3);

    // A próxima resposta traz uma etapa nova: o intervalo recomeça em 1000 ms.
    getRun().mockResolvedValue(running({ progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo')] } }));
    await advance(DEFAULT_POLL_SCHEDULE[2]);
    expect(getRun()).toHaveBeenCalledTimes(4);
    await advance(DEFAULT_POLL_SCHEDULE[0]);
    expect(getRun()).toHaveBeenCalledTimes(5);
  });

  it('preserva o último estado enquanto a próxima consulta está em andamento', async () => {
    getRun().mockResolvedValueOnce(running({ progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo')] } }));
    // A segunda consulta nunca responde: o estado anterior tem de continuar visível.
    getRun().mockImplementationOnce(() => new Promise<AiRun>(() => {}));
    const { result } = renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    expect(result.current.run?.progress?.stage).toBe('reading');

    await advance(DEFAULT_POLL_SCHEDULE[0]);
    expect(getRun()).toHaveBeenCalledTimes(2);
    expect(result.current.run?.progress?.stage).toBe('reading');
    expect(result.current.loading).toBe(false);
  });

  it.each(['completed', 'failed', 'cancelled', 'waiting_review'] as const)('para de consultar em %s', async status => {
    getRun().mockResolvedValueOnce(running());
    getRun().mockResolvedValue(makeRun({ status, progress: { stage: status === 'waiting_review' ? 'waiting_review' : 'done', steps: [] } }));
    const { result } = renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    await advance(DEFAULT_POLL_SCHEDULE[0]);
    expect(result.current.run?.status).toBe(status);
    expect(result.current.polling).toBe(false);

    await advance(120_000);
    expect(getRun()).toHaveBeenCalledTimes(2);
  });

  it('continua em queued, running e needs_reconciliation; para nos demais', () => {
    expect((['queued', 'running', 'needs_reconciliation'] as const).map(shouldKeepPolling)).toEqual([true, true, true]);
    expect((['waiting_review', 'completed', 'failed', 'cancelled'] as const).map(shouldKeepPolling)).toEqual([false, false, false, false]);
  });

  it('aborta a consulta em voo e cancela o agendamento ao desmontar', async () => {
    getRun().mockResolvedValue(running());
    const { unmount } = renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    const signal = getRun().mock.calls[0][1]!.signal!;
    expect(signal.aborted).toBe(false);

    unmount();
    expect(signal.aborted).toBe(true);
    await advance(120_000);
    expect(getRun()).toHaveBeenCalledTimes(1);
  });

  it('falha passageira mantém o último estado, tenta de novo e depois devolve a decisão', async () => {
    getRun().mockResolvedValueOnce(running({ progress: { stage: 'reading', steps: [] } }));
    getRun().mockRejectedValue(transient());
    const { result } = renderHook(() => useRunPolling('run-0001'));
    await advance(0);

    await advance(DEFAULT_POLL_SCHEDULE[0]);
    expect(result.current.error?.traceId).toBe('rastreio-0503');
    expect(result.current.run?.progress?.stage).toBe('reading');
    expect(result.current.polling).toBe(true);

    await advance(120_000);
    // 1 sucesso + o máximo de falhas seguidas; depois disso, silêncio.
    expect(getRun()).toHaveBeenCalledTimes(1 + MAX_CONSECUTIVE_FAILURES);
    expect(result.current.polling).toBe(false);
    expect(result.current.run?.progress?.stage).toBe('reading');
  });

  it('erro definitivo não é repetido', async () => {
    getRun().mockRejectedValue(new AiApiError({ code: 'not_found', retryable: false, safeMessage: 'Recurso não encontrado.', status: 404 }));
    const { result } = renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    await advance(120_000);
    expect(getRun()).toHaveBeenCalledTimes(1);
    expect(result.current).toMatchObject({ run: null, polling: false, loading: false });
    expect(result.current.error?.code).toBe('not_found');
  });

  it('refresh retoma a consulta sem apagar o que está na tela', async () => {
    getRun().mockResolvedValueOnce(makeRun({ status: 'waiting_review', progress: { stage: 'waiting_review', steps: [] } }));
    const { result } = renderHook(() => useRunPolling('run-0001'));
    await advance(0);
    expect(result.current.polling).toBe(false);

    let release!: (run: AiRun) => void;
    getRun().mockImplementationOnce(() => new Promise<AiRun>(resolve => { release = resolve; }));
    act(() => result.current.refresh());
    expect(getRun()).toHaveBeenCalledTimes(2);
    expect(result.current.run?.status).toBe('waiting_review');

    await act(async () => { release(makeRun({ status: 'completed', progress: { stage: 'done', steps: [] } })); });
    expect(result.current.run?.status).toBe('completed');
  });

  it('trocar de execução nunca mostra dados da anterior', async () => {
    getRun().mockResolvedValueOnce(makeRun({ run_id: 'run-0001', status: 'completed', summary_pt_br: 'Resposta da primeira.' }));
    getRun().mockImplementationOnce(() => new Promise<AiRun>(() => {}));
    const { result, rerender } = renderHook(({ id }) => useRunPolling(id), { initialProps: { id: 'run-0001' as string | null } });
    await advance(0);
    expect(result.current.run?.summary_pt_br).toBe('Resposta da primeira.');

    rerender({ id: 'run-0002' });
    expect(result.current.run).toBeNull();
    expect(result.current.loading).toBe(true);
    expect(getRun()).toHaveBeenLastCalledWith('run-0002', expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it('sem execução selecionada não consulta nada', async () => {
    const { result } = renderHook(() => useRunPolling(null));
    await advance(60_000);
    expect(getRun()).not.toHaveBeenCalled();
    expect(result.current).toMatchObject({ run: null, loading: false, polling: false });
  });
});
