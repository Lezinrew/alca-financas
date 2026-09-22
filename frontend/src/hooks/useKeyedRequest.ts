import { useEffect, useRef, useState } from 'react';

export interface KeyedResult<T> {
  data: T | null;
  loading: boolean;
  error: string;
}

export const REQUEST_ERROR_MESSAGE = 'Não foi possível atualizar. Tente novamente.';

/**
 * Executa `request` sempre que `key` muda, cancelando a requisição anterior.
 * Um resultado só é exibido quando pertence à chave atual: dados de um filtro
 * antigo nunca aparecem como se fossem os atuais, e um erro nunca vira "vazio".
 */
export function useKeyedRequest<T>(
  key: string,
  enabled: boolean,
  request: (signal: AbortSignal) => Promise<{ data: T }>,
): KeyedResult<T> {
  const requestRef = useRef(request);
  requestRef.current = request;
  const [state, setState] = useState<KeyedResult<T> & { key: string }>({ key: '', data: null, loading: false, error: '' });

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let active = true;
    setState({ key, data: null, loading: true, error: '' });
    void requestRef.current(controller.signal).then(({ data }) => {
      if (active) setState({ key, data, loading: false, error: '' });
    }).catch(() => {
      if (active && !controller.signal.aborted) {
        setState({ key, data: null, loading: false, error: REQUEST_ERROR_MESSAGE });
      }
    });
    return () => { active = false; controller.abort(); };
  }, [key, enabled]);

  if (!enabled) return { data: null, loading: false, error: '' };
  if (state.key !== key) return { data: null, loading: true, error: '' };
  return { data: state.data, loading: state.loading, error: state.error };
}
