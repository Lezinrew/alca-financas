import { useCallback, useEffect, useRef, useState } from 'react';
import { type AiApiError, isAbort, toAiApiError } from './aiErrors';

export interface AiRequest<T> {
  data: T | null;
  loading: boolean;
  error: AiApiError | null;
  /** Repete a consulta mantendo na tela o resultado anterior da mesma chave. */
  reload: () => void;
}

/**
 * Consulta única por chave (status, histórico, propostas, operações).
 *
 * Parecido com `useKeyedRequest`, com duas diferenças necessárias aqui:
 *  - o erro é um `AiApiError`, para a tela mostrar `safe_message` e o código de
 *    rastreio em vez de um texto fixo;
 *  - `reload()` atualiza sem apagar o que já está visível.
 * Como lá, a resposta de uma chave antiga é descartada e erro nunca vira "vazio".
 * `key = null` desliga a consulta.
 */
export function useAiRequest<T>(key: string | null, request: (signal: AbortSignal) => Promise<T>): AiRequest<T> {
  const requestRef = useRef(request);
  requestRef.current = request;
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{ key: string | null; data: T | null; loading: boolean; error: AiApiError | null }>(
    { key: null, data: null, loading: false, error: null },
  );

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    let active = true;
    // Recarga da mesma chave: dados E erro anteriores ficam visíveis até a nova
    // resposta chegar, para a tela não piscar nem perder o foco do botão de repetir.
    setState(previous => previous.key === key
      ? { ...previous, loading: true }
      : { key, data: null, loading: true, error: null });
    requestRef.current(controller.signal).then(data => {
      if (active) setState({ key, data, loading: false, error: null });
    }).catch((error: unknown) => {
      if (!active || isAbort(error)) return;
      setState(previous => ({ key, data: previous.key === key ? previous.data : null, loading: false, error: toAiApiError(error) }));
    });
    return () => { active = false; controller.abort(); };
  }, [key, revision]);

  const reload = useCallback(() => setRevision(value => value + 1), []);

  if (key === null) return { data: null, loading: false, error: null, reload };
  if (state.key !== key) return { data: null, loading: true, error: null, reload };
  return { data: state.data, loading: state.loading, error: state.error, reload };
}
