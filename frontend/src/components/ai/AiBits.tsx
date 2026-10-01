import { useId } from 'react';
import { FileCheck2, FileInput, Link2, PenLine, Undo2, type LucideIcon } from 'lucide-react';
import type { AiApiError } from './aiErrors';
import { LEDGER_STATES, ledgerStateInfo, spaceKindLabel } from './aiFormat';
import type { LedgerState, SpaceKind } from './aiTypes';

/**
 * Erro em linguagem do titular: a mensagem segura do servidor e o código de
 * rastreio (para ele informar ao suporte). Nenhum detalhe técnico é exibido.
 */
export function ErrorNotice({ error, title, onRetry, retryLabel = 'Tentar novamente' }: {
  error: AiApiError;
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return <div className="ai-error" role="alert">
    {title && <p className="ai-error-title">{title}</p>}
    <p>{error.safeMessage}</p>
    {error.traceId && <p className="ai-trace-line">Código de rastreio: <code className="ai-code">{error.traceId}</code></p>}
    {onRetry && <button type="button" className="ai-button" onClick={onRetry}>{retryLabel}</button>}
  </div>;
}

/** Pessoal x negócio sempre por extenso: a cor sozinha não identifica o espaço. */
export function SpaceKindBadge({ kind }: { kind?: SpaceKind | null }) {
  return <span className={`ai-badge ai-space-${kind === 'business' ? 'business' : kind === 'family' ? 'family' : 'personal'}`}>{spaceKindLabel(kind)}</span>;
}

// Cada estado tem ícone, cor E rótulo próprios: quem não distingue cores ou usa
// leitor de tela ainda diferencia os três.
const LEDGER_ICONS: Record<string, LucideIcon> = {
  conferido: FileCheck2, registrado_pago: PenLine, conciliado: Link2, importado: FileInput, revertido: Undo2,
};

export function LedgerStateBadge({ state }: { state?: LedgerState | null }) {
  const info = ledgerStateInfo(state);
  if (!info) return <span className="ai-badge">Estado não informado</span>;
  const Icon = LEDGER_ICONS[info.id] ?? FileCheck2;
  return <span className={`ai-badge ai-ledger ai-ledger-${info.id}`}><Icon size={16} aria-hidden="true" />{info.label}</span>;
}

/** Texto curto que explica a diferença entre os três estados. */
export function StateLegend() {
  const titleId = useId();
  return <section className="ai-legend" aria-labelledby={titleId}>
    <h3 id={titleId}>Três estados que não são a mesma coisa</h3>
    <dl>
      {LEDGER_STATES.map(item => <div key={item.id}>
        <dt><LedgerStateBadge state={item.id} /></dt>
        <dd>{item.explanation}</dd>
      </div>)}
    </dl>
  </section>;
}

/** Identificadores e hashes: fonte monoespaçada e quebra em qualquer ponto (cabem em 360 px). */
export function Code({ children }: { children: string }) {
  return <code className="ai-code">{children}</code>;
}
