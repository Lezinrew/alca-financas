import { Undo2 } from 'lucide-react';
import { Code, SpaceKindBadge } from './AiBits';
import { EffectSummary } from './EffectSummary';
import { formatInstant, proposalKindLabel } from './aiFormat';
import type { AiOperation } from './aiTypes';

/**
 * O que foi efetivamente gravado, segundo o servidor.
 *
 * "Desfazer" não apaga histórico: pede ao servidor uma proposta de compensação,
 * que passa pela mesma revisão e aprovação de qualquer outra gravação.
 */
export function OperationCard({ operation, writeDisabled, onUndo }: {
  operation: AiOperation;
  writeDisabled: boolean;
  onUndo: (operation: AiOperation) => void;
}) {
  const space = operation.scope?.financial_space;
  const accounts = operation.scope?.accounts ?? [];
  const appliedAt = formatInstant(operation.applied_at);
  const reversedAt = formatInstant(operation.reversed_at);
  const reversed = operation.status === 'reversed';
  // Uma compensação já é o "desfazer" de outra operação; não oferecemos desfazer em cadeia.
  const canUndo = operation.status === 'applied' && operation.kind !== 'reverse_operation';

  return <article className="ai-proposal" aria-label={`Operação gravada: ${proposalKindLabel(operation.kind)}`}>
    <div className="ai-row ai-row-between">
      <h3>{proposalKindLabel(operation.kind)}</h3>
      <span className={`ai-badge ai-operation-${reversed ? 'reversed' : 'applied'}`}>{reversed ? 'Desfeita' : 'Gravada'}</span>
    </div>
    {operation.summary_pt_br && <p className="ai-summary">{operation.summary_pt_br}</p>}

    <dl className="ai-pairs">
      <div><dt>Operação</dt><dd><Code>{operation.operation_id}</Code></dd></div>
      {appliedAt && <div><dt>Gravada em</dt><dd>{appliedAt} (horário de Brasília)</dd></div>}
      {reversedAt && <div><dt>Desfeita em</dt><dd>{reversedAt} (horário de Brasília)</dd></div>}
      {space && <div><dt>Espaço financeiro</dt><dd>{space.name} <SpaceKindBadge kind={space.kind} /></dd></div>}
      {accounts.length > 0 && <div><dt>Conta</dt><dd>{accounts.map(account => account.name).join(', ')}</dd></div>}
    </dl>

    <EffectSummary effect={operation.effect} applied caption="O que foi gravado: antes e depois" />
    <p className="ai-muted ai-small">O registro foi feito no aplicativo. Nenhum dinheiro foi movimentado no banco.</p>

    {canUndo && <>
      <div className="ai-actions">
        <button type="button" className="ai-button ai-button-danger" disabled={writeDisabled} onClick={() => onUndo(operation)}>
          <Undo2 size={16} aria-hidden="true" />Desfazer
        </button>
      </div>
      <p className="ai-muted ai-small">{writeDisabled
        ? 'A gravação pelo operador está desativada no servidor; não é possível desfazer por aqui agora.'
        : 'Desfazer cria uma proposta de compensação, que também precisa da sua aprovação. O histórico é preservado.'}</p>
    </>}
  </article>;
}
