import { forwardRef } from 'react';
import { Code } from './AiBits';
import { formatInstant, stepStatusLabel, taskLabel } from './aiFormat';
import type { AiOperation, AiProposal, AiRun } from './aiTypes';

const STEP_KIND: Record<string, string> = { tool: 'Ferramenta', inference: 'Modelo' };

/**
 * "Rastrear": o que o titular precisa para acompanhar ou pedir suporte.
 *
 * Mostra identificadores e etapas, nunca conteúdo de e-mail, prompt ou resposta
 * bruta do modelo. O código de rastreio é o mesmo que aparece nas mensagens de
 * erro e liga esta tela aos registros do servidor.
 */
export const TracePanel = forwardRef<HTMLHeadingElement, {
  id: string;
  run: AiRun;
  proposals: AiProposal[];
  operations: AiOperation[];
}>(function TracePanel({ id, run, proposals, operations }, headingRef) {
  const steps = run.progress?.steps ?? [];
  const created = formatInstant(run.created_at);
  const finished = formatInstant(run.finished_at);
  const model = run.model;

  return <section id={id} className="ai-panel ai-trace" aria-labelledby={`${id}-title`}>
    <h2 id={`${id}-title`} ref={headingRef} tabIndex={-1}>Rastreio</h2>
    <dl className="ai-pairs">
      <div><dt>Código de rastreio</dt><dd>{run.trace_id ? <Code>{run.trace_id}</Code> : 'Não informado'}</dd></div>
      <div><dt>Execução</dt><dd><Code>{run.run_id}</Code></dd></div>
      <div><dt>Tarefa</dt><dd>{taskLabel(run.task)}</dd></div>
      {created && <div><dt>Início</dt><dd>{created}</dd></div>}
      {finished && <div><dt>Fim</dt><dd>{finished}</dd></div>}
      <div><dt>Modelo usado</dt><dd>{model?.alias ? `${model.alias}${model.provider ? ` (${model.provider})` : ''}` : 'Nenhum modelo informado'}</dd></div>
      {run.contract_version && <div><dt>Versão do contrato</dt><dd>{run.contract_version}</dd></div>}
    </dl>

    {model?.fallback_used && <p className="ai-notice">O modelo preferido não estava disponível e o servidor usou um modelo alternativo nesta execução.</p>}

    <h3>Etapas</h3>
    {steps.length === 0
      ? <p className="ai-muted">Nenhuma etapa relatada até agora.</p>
      : <ol className="ai-trace-steps">
        {steps.map(step => {
          const started = formatInstant(step.started_at);
          return <li key={step.seq}>
            <span>{step.seq}. {step.label || step.name}</span>
            <span className="ai-muted ai-small">{STEP_KIND[step.kind] ?? step.kind}: <Code>{step.name}</Code> · {stepStatusLabel(step.status)}{started ? ` · ${started}` : ''}</span>
          </li>;
        })}
      </ol>}

    {proposals.length > 0 && <>
      <h3>Propostas</h3>
      <ul className="ai-plain-list">
        {proposals.map(proposal => <li key={proposal.proposal_id}>
          <dl className="ai-pairs ai-pairs-compact">
            <div><dt>Proposta</dt><dd><Code>{proposal.proposal_id}</Code></dd></div>
            <div><dt>Versão</dt><dd>{proposal.version}</dd></div>
            <div><dt>Hash do conteúdo</dt><dd><Code>{proposal.payload_hash}</Code></dd></div>
          </dl>
        </li>)}
      </ul>
    </>}

    {operations.length > 0 && <>
      <h3>Operações</h3>
      <ul className="ai-plain-list">
        {operations.map(operation => <li key={operation.operation_id}><Code>{operation.operation_id}</Code></li>)}
      </ul>
    </>}
  </section>;
});
