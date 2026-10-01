import { ErrorNotice } from './AiBits';
import type { AiApiError } from './aiErrors';
import { formatInstant, runStatusLabel, taskLabel } from './aiFormat';
import type { AiRunSummary } from './aiTypes';

/**
 * Histórico curto das execuções recentes do espaço em uso.
 *
 * Três estados nunca se confundem: carregando, falha (com nova tentativa) e
 * vazio de verdade. Uma falha não pode aparecer como "nenhuma execução".
 */
export function RunHistory({ runs, loading, error, activeRunId, onOpen, onRetry }: {
  runs: AiRunSummary[] | null;
  loading: boolean;
  error: AiApiError | null;
  activeRunId: string | null;
  onOpen: (runId: string) => void;
  onRetry: () => void;
}) {
  return <section className="ai-panel" aria-labelledby="ai-history-title" aria-busy={loading}>
    <h2 id="ai-history-title">Execuções recentes</h2>
    {error
      ? <ErrorNotice error={error} title="Histórico indisponível." onRetry={onRetry} />
      : runs === null
        ? <p role="status">Carregando histórico…</p>
        : runs.length === 0
          ? <p className="ai-muted">Nenhuma execução ainda. Faça um pedido para começar.</p>
          : <ul className="ai-history">
            {runs.map(run => {
              const when = formatInstant(run.created_at);
              const label = taskLabel(run.task);
              const current = run.run_id === activeRunId;
              return <li key={run.run_id}>
                <div className="ai-history-text">
                  <span className="ai-history-task">{label}</span>
                  <span className="ai-muted ai-small">{when ?? 'Data não informada'}</span>
                  {run.summary_pt_br && <span className="ai-small ai-history-summary">{run.summary_pt_br}</span>}
                </div>
                <span className={`ai-badge ai-status-${run.status}`}>{runStatusLabel(run.status)}</span>
                <button type="button" className="ai-button" aria-pressed={current} aria-label={`Abrir execução: ${label}${when ? `, ${when}` : ''}`} onClick={() => onOpen(run.run_id)}>
                  {current ? 'Aberta' : 'Abrir'}
                </button>
              </li>;
            })}
          </ul>}
  </section>;
}
