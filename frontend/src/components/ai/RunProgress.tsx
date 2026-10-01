import { Ban, Circle, CircleCheck, CircleDot, CircleX, Hourglass, type LucideIcon } from 'lucide-react';
import { ErrorNotice, SpaceKindBadge } from './AiBits';
import { AiApiError } from './aiErrors';
import { buildStages, runStatusLabel, stageStateText, stepStatusLabel, taskLabel, type StageState } from './aiFormat';
import type { AiRun } from './aiTypes';

const STAGE_ICONS: Record<StageState, LucideIcon> = {
  done: CircleCheck, current: CircleDot, waiting: Hourglass, pending: Circle, failed: CircleX, cancelled: Ban,
};

/**
 * Só o que o servidor de fato cancela. Em `waiting_review` o cancelamento não
 * muda nada (a execução espera a decisão sobre a proposta, e é a proposta que se
 * rejeita); oferecer o botão ali seria um clique sem efeito e sem resposta.
 */
const CANCELLABLE = new Set(['queued', 'running']);

/** Frase única para o leitor de tela: o que está acontecendo agora, segundo o servidor. */
const liveSentence = (run: AiRun): string => {
  if (run.status === 'completed') return 'Execução concluída.';
  if (run.status === 'failed') return 'A execução falhou.';
  if (run.status === 'cancelled') return 'Execução cancelada.';
  if (run.status === 'waiting_review') return 'Aguardando a sua revisão.';
  if (run.status === 'needs_reconciliation') return 'Conferindo o resultado da gravação.';
  if (run.status === 'queued') return 'Na fila: a execução ainda não começou.';
  const current = buildStages(run).find(stage => stage.state === 'current');
  const steps = run.progress?.steps ?? [];
  const lastStep = steps[steps.length - 1];
  if (current && lastStep?.label) return `${current.label}: ${lastStep.label}.`;
  if (current) return `${current.label}.`;
  return 'Em andamento.';
};

/**
 * Andamento REAL da execução.
 *
 * Tudo vem de `progress.stage` e `progress.steps` do servidor. Não há barra que
 * avança sozinha nem animação de "pensando": se o servidor não relatou avanço,
 * a tela não finge. O anúncio acessível é uma frase curta em `role="status"`
 * (aria-live polite): muda só quando a etapa muda, sem ler a lista inteira.
 */
export function RunProgress({ run, requestText, polling, pollError, onRetry, onRefresh, onCancel, cancelling, cancelError, traceOpen, traceId, onToggleTrace }: {
  run: AiRun;
  requestText?: string;
  polling: boolean;
  pollError: AiApiError | null;
  onRetry: () => void;
  /** Reconsulta a execução e o que ela mostra (propostas, operações). */
  onRefresh: () => void;
  onCancel: () => void;
  cancelling: boolean;
  cancelError: AiApiError | null;
  traceOpen: boolean;
  traceId: string;
  onToggleTrace: () => void;
}) {
  const stages = buildStages(run);
  const steps = run.progress?.steps ?? [];
  const space = run.scope?.financial_space;
  const accounts = run.scope?.accounts ?? [];
  const runError = run.error
    ? new AiApiError({ code: run.error.code, retryable: run.error.retryable, safeMessage: run.error.safe_message, traceId: run.error.trace_id ?? run.trace_id })
    : null;

  return <div className="ai-stack">
    <div className="ai-row ai-row-between">
      <p className="ai-run-title"><strong>{taskLabel(run.task)}</strong> <span className={`ai-badge ai-status-${run.status}`}>{runStatusLabel(run.status)}</span></p>
      {space && <p className="ai-scope-line"><span className="ai-muted">Espaço:</span> {space.name} <SpaceKindBadge kind={space.kind} /></p>}
    </div>
    {accounts.length > 0 && <p className="ai-muted ai-small">Contas no alcance: {accounts.map(account => account.name).join(', ')}</p>}
    {requestText && <p className="ai-quote"><span className="ai-muted">Pedido:</span> {requestText}</p>}

    <ol className="ai-stages" aria-label="Etapas da execução">
      {stages.map(stage => {
        const Icon = STAGE_ICONS[stage.state];
        return <li key={stage.id} className={`ai-stage ai-stage-${stage.state}`} aria-current={stage.state === 'current' || stage.state === 'waiting' ? 'step' : undefined}>
          <Icon size={20} aria-hidden="true" />
          <span className="ai-stage-text"><span className="ai-stage-label">{stage.label}</span><span className="ai-stage-state">{stageStateText(stage.state)}</span></span>
        </li>;
      })}
    </ol>

    <p role="status" aria-live="polite" className="ai-live">{liveSentence(run)}</p>

    {steps.length > 0 && <ol className="ai-steps" aria-label="Passos já relatados pelo servidor">
      {steps.map(step => <li key={step.seq}>
        <span>{step.label || step.name}</span>
        <span className={`ai-step-status ai-step-${step.status}`}>{stepStatusLabel(step.status)}</span>
      </li>)}
    </ol>}

    {run.status === 'waiting_review' && <p className="ai-muted ai-small">{'Esta execução aguarda a sua decisão sobre a proposta abaixo. Se não quiser gravar, use "Corrigir" para rejeitar a proposta: nada é gravado.'}</p>}
    {run.cancel_requested && run.status !== 'cancelled' && <p className="ai-notice">Cancelamento solicitado. O que já foi confirmado permanece e pode ser desfeito.</p>}
    {run.status === 'needs_reconciliation' && <p className="ai-notice">O servidor ainda está confirmando se a gravação foi concluída. Não repita o pedido: esta tela continua acompanhando.</p>}
    {runError && <ErrorNotice error={runError} title="A execução não foi concluída." />}
    {pollError && (polling
      ? <p className="ai-notice" role="status">Sem resposta do servidor. Tentando de novo; o último estado conhecido continua acima.</p>
      : <ErrorNotice error={pollError} title="Não foi possível atualizar o andamento. O último estado conhecido continua acima." onRetry={onRetry} />)}
    {cancelError && <ErrorNotice error={cancelError} title="O cancelamento não foi confirmado." />}

    <div className="ai-actions">
      {CANCELLABLE.has(run.status) && <button type="button" className="ai-button ai-button-danger" onClick={onCancel} disabled={cancelling || !!run.cancel_requested}>
        <Ban size={16} aria-hidden="true" />{cancelling ? 'Cancelando…' : 'Cancelar'}
      </button>}
      {/* Em "aguardando revisão" a tela não consulta sozinha (a próxima mudança costuma
          depender do titular). Se a decisão veio de outro lugar, ou a gravação de uma
          proposta aprovada ainda não tinha terminado, este botão traz o estado atual. */}
      {run.status === 'waiting_review' && <button type="button" className="ai-button" onClick={onRefresh} disabled={polling}>Atualizar</button>}
      <button type="button" className="ai-button" aria-expanded={traceOpen} aria-controls={traceId} onClick={onToggleTrace}>Rastrear</button>
    </div>
  </div>;
}
