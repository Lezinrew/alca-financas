import { TriangleAlert } from 'lucide-react';
import { Code, SpaceKindBadge } from './AiBits';
import { EffectSummary } from './EffectSummary';
import { evidenceKindLabel, formatInstant, formatPeriod, originKindLabel, proposalKindLabel, proposalStatusLabel } from './aiFormat';
import type { AiProposal } from './aiTypes';

const OPEN = new Set(['draft', 'ready']);
const REDO = new Set(['stale', 'expired']);

/** O relógio do navegador só serve para avisar; quem decide se expirou é o servidor. */
const isPast = (instant?: string | null) => {
  if (!instant) return false;
  const time = new Date(instant).getTime();
  return !Number.isNaN(time) && time < Date.now();
};

/**
 * Prévia de uma alteração antes de gravar.
 *
 * Mostra tudo o que o titular precisa para decidir: de onde veio, onde vai
 * gravar, o efeito antes -> depois, o que ficou ambíguo e até quando vale.
 * Nada é gravado por esta tela sem o clique em "Aprovar" e a confirmação.
 */
export function ProposalCard({ proposal, writeDisabled, onApprove, onCorrect, onRedo, onTrace }: {
  proposal: AiProposal;
  /** Servidor informou que a escrita pelo operador está desligada. */
  writeDisabled: boolean;
  onApprove: (proposal: AiProposal) => void;
  onCorrect: (proposal: AiProposal) => void;
  onRedo: (proposal: AiProposal) => void;
  onTrace: () => void;
}) {
  const space = proposal.scope?.financial_space;
  const accounts = proposal.scope?.accounts ?? [];
  const ambiguities = proposal.ambiguities ?? [];
  const evidence = proposal.evidence ?? [];
  const period = formatPeriod(proposal.origin?.period);
  const expires = formatInstant(proposal.expires_at);
  const expired = proposal.status === 'expired' || (OPEN.has(proposal.status) && isPast(proposal.expires_at));
  const canDecide = OPEN.has(proposal.status) && !expired;
  const canApprove = canDecide && proposal.status === 'ready' && !writeDisabled;
  const kind = proposalKindLabel(proposal.kind);

  return <article className="ai-proposal" aria-label={`Proposta: ${kind}`}>
    <div className="ai-row ai-row-between">
      <h3>{kind}</h3>
      <span className={`ai-badge ai-proposal-${expired ? 'expired' : proposal.status}`}>{expired ? 'Expirada' : proposalStatusLabel(proposal.status)}</span>
    </div>
    {proposal.summary_pt_br && <p className="ai-summary">{proposal.summary_pt_br}</p>}

    <dl className="ai-pairs">
      <div><dt>Origem</dt><dd>{originKindLabel(proposal.origin?.source_kind)}{proposal.origin?.label ? <> · <span className="ai-break">{proposal.origin.label}</span></> : null}</dd></div>
      <div><dt>Período</dt><dd>{period ?? 'Não informado'}</dd></div>
      <div><dt>Espaço financeiro</dt><dd>{space ? <>{space.name} <SpaceKindBadge kind={space.kind} /></> : 'Não informado'}</dd></div>
      <div><dt>Conta</dt><dd>{accounts.length ? accounts.map(account => account.name).join(', ') : 'Não informada'}</dd></div>
      <div><dt>Validade</dt><dd>{expires ? `${expired ? 'Expirou em' : 'Vale até'} ${expires} (horário de Brasília)` : 'Não informada'}</dd></div>
    </dl>

    <EffectSummary effect={proposal.effect} caption="Impacto: antes e depois de aplicar" />

    {/* Ambiguidade nunca fica escondida: é o motivo de a proposta pedir revisão humana. */}
    {ambiguities.length > 0 && <div className="ai-warning" role="note">
      <p className="ai-warning-title"><TriangleAlert size={18} aria-hidden="true" />{ambiguities.length === 1 ? '1 ponto ambíguo precisa da sua revisão' : `${ambiguities.length} pontos ambíguos precisam da sua revisão`}</p>
      <ul className="ai-plain-list">{ambiguities.map((item, index) => <li key={`${item.code ?? 'ambiguity'}-${index}`}>
        {item.blocking && <strong>Impede a aprovação: </strong>}{item.message}
      </li>)}</ul>
    </div>}
    {proposal.requires_review && <p className="ai-notice">Esta proposta só pode ser aplicada com a sua aprovação, mesmo que exista uma autorização permanente.</p>}

    <div className="ai-block">
      <h4>Evidências</h4>
      {evidence.length === 0
        ? <p className="ai-muted">Nenhuma evidência foi anexada a esta proposta.</p>
        : <ul className="ai-plain-list">{evidence.map((item, index) => <li key={`${item.ref}-${index}`}>{evidenceKindLabel(item.kind)}: <Code>{item.ref}</Code></li>)}</ul>}
    </div>

    {canDecide && writeDisabled && <p className="ai-notice">A gravação pelo operador está desativada no servidor. Você pode revisar e corrigir, mas não aprovar.</p>}
    {/* No backend, `draft` não é "ainda preparando": é uma prévia com pendência que impede a
        aprovação. Ela não fica pronta sozinha; só um novo pedido gera outra prévia. */}
    {canDecide && proposal.status === 'draft' && <p className="ai-notice">{'Esta proposta tem pendências que impedem a aprovação. Use "Corrigir" para refazer o pedido e gerar uma nova prévia.'}</p>}
    {proposal.status === 'approved' && <p className="ai-notice">{'Proposta aprovada. A gravação aparece em "Resultado aplicado" quando o servidor confirmar.'}</p>}
    {proposal.status === 'stale' && <p className="ai-notice">Os dados mudaram depois que esta proposta foi preparada. Refaça o pedido para gerar uma prévia atual.</p>}
    {expired && <p className="ai-notice">A proposta expirou sem ser aplicada. Refaça o pedido se ainda precisar dela.</p>}

    <div className="ai-actions">
      {canDecide && <button type="button" className="ai-button ai-button-primary" disabled={!canApprove} onClick={() => onApprove(proposal)}>Aprovar</button>}
      {canDecide && <button type="button" className="ai-button" onClick={() => onCorrect(proposal)}>Corrigir</button>}
      {(REDO.has(proposal.status) || expired) && <button type="button" className="ai-button" onClick={() => onRedo(proposal)}>Refazer pedido</button>}
      <button type="button" className="ai-button" onClick={onTrace}>Rastrear</button>
    </div>
  </article>;
}
