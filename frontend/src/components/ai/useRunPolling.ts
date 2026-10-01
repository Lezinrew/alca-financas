import { useCallback, useEffect, useRef, useState } from 'react';
import { aiApi } from './aiApi';
import { type AiApiError, isAbort, toAiApiError } from './aiErrors';
import type { AiRun, RunStatus } from './aiTypes';

/**
 * Intervalos entre consultas, em milissegundos. Crescem enquanto nada muda,
 * para não martelar o servidor em uma execução longa, e voltam ao início
 * quando o servidor relata progresso (nova etapa, novo estado).
 */
export const DEFAULT_POLL_SCHEDULE: readonly number[] = [1000, 1500, 2500, 4000, 6000, 8000];

/** Falhas seguidas toleradas antes de parar e pedir "Tentar novamente". */
export const MAX_CONSECUTIVE_FAILURES = 3;

/**
 * Só estes estados ainda mudam sem ação do titular.
 * `waiting_review` para o polling: a próxima mudança depende de aprovar ou
 * rejeitar, e a tela reconsulta depois dessa ação. `completed`, `failed` e
 * `cancelled` são finais.
 */
export const shouldKeepPolling = (status: RunStatus): boolean =>
  status === 'queued' || status === 'running' || status === 'needs_reconciliation';

export interface RunPolling {
  run: AiRun | null;
  /** Falha da última consulta. O último `run` conhecido continua disponível. */
  error: AiApiError | null;
  /** Primeira consulta em andamento, ainda sem nenhum estado para mostrar. */
  loading: boolean;
  /** Há uma próxima consulta agendada ou em andamento. */
  polling: boolean;
  /** Consulta agora e retoma o ciclo (após falha, aprovação, cancelamento...). */
  refresh: () => void;
}

interface State {
  runId: string | null;
  run: AiRun | null;
  error: AiApiError | null;
  polling: boolean;
}

/**
 * Acompanha uma execução consultando `GET /runs/{id}`.
 *
 * Por que não `useKeyedRequest`: ele zera `data` a cada mudança de chave, então
 * usar um contador na chave faria a tela piscar ("carregando") a cada consulta.
 * Aqui o último estado conhecido é preservado entre consultas e também quando
 * uma consulta falha: a tela nunca troca progresso real por vazio.
 */
export function useRunPolling(runId: string | null, options: { schedule?: readonly number[] } = {}): RunPolling {
  const schedule = options.schedule && options.schedule.length > 0 ? options.schedule : DEFAULT_POLL_SCHEDULE;
  const scheduleRef = useRef(schedule);
  scheduleRef.current = schedule;
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<State>({ runId: null, run: null, error: null, polling: false });

  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active = true;
    let attempt = 0;
    let failures = 0;
    let lastMarker = '';

    // Mesma execução (refresh): mantém o que já está na tela. Outra execução: começa limpo,
    // para nunca mostrar dados de uma execução como se fossem de outra.
    setState(previous => previous.runId === runId
      ? { ...previous, error: null, polling: true }
      : { runId, run: null, error: null, polling: true });

    const scheduleNext = () => {
      const steps = scheduleRef.current;
      const delay = steps[Math.min(attempt, steps.length - 1)];
      attempt += 1;
      timer = setTimeout(() => { void tick(); }, delay);
    };

    const tick = async () => {
      try {
        const run = await aiApi.getRun(runId, { signal: controller.signal });
        if (!active) return;
        failures = 0;
        const marker = `${run.status}|${run.progress?.stage ?? ''}|${run.progress?.steps?.length ?? 0}`;
        if (marker !== lastMarker) { attempt = 0; lastMarker = marker; }
        const keep = shouldKeepPolling(run.status);
        setState({ runId, run, error: null, polling: keep });
        if (keep) scheduleNext();
      } catch (error) {
        if (!active || isAbort(error)) return;
        const apiError = toAiApiError(error);
        failures += 1;
        // Erro definitivo (401, 403, 404...) não melhora repetindo; erro passageiro
        // ganha algumas tentativas antes de devolver a decisão ao titular.
        const retry = apiError.retryable && failures < MAX_CONSECUTIVE_FAILURES;
        setState(previous => ({ runId, run: previous.runId === runId ? previous.run : null, error: apiError, polling: retry }));
        if (retry) scheduleNext();
      }
    };

    void tick();
    // Ao desmontar ou trocar de execução: cancela a consulta em voo e o próximo agendamento.
    return () => { active = false; controller.abort(); if (timer !== undefined) clearTimeout(timer); };
  }, [runId, revision]);

  const refresh = useCallback(() => setRevision(value => value + 1), []);

  if (!runId) return { run: null, error: null, loading: false, polling: false, refresh };
  if (state.runId !== runId) return { run: null, error: null, loading: true, polling: true, refresh };
  return { run: state.run, error: state.error, loading: !state.run && !state.error, polling: state.polling, refresh };
}
