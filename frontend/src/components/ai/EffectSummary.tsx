import { LedgerStateBadge } from './AiBits';
import { DASH, effectCounts, effectTotals, formatDecimalMoney, payableStatusLabel } from './aiFormat';
import type { ProposalEffect } from './aiTypes';

// Em colunas estreitas (360 px) o valor pode quebrar entre "R$" e o número; por isso
// aqui o espaço não separável vira espaço comum. Sem isso o navegador quebraria no
// meio do número.
const NBSP = String.fromCharCode(160);
const breakable = (text: string) => text.replace(NBSP, ' ');
// Ausência (campo nulo ou fora do formato) é travessão. "R$ 0,00" aqui afirmaria um
// saldo que o servidor não informou.
const money = (value: unknown) => breakable(formatDecimalMoney(value) ?? DASH);

/**
 * Impacto de uma proposta ou de uma operação já aplicada.
 *
 * Baixa: tabela antes -> depois (pago, restante, situação).
 * Importação: itens novos, duplicados, transferências que ficam de fora e totais.
 * `applied` troca o tempo dos rótulos e o cabeçalho da tabela: "Depois" enquanto
 * é proposta, "Gravado" quando o efeito já foi confirmado pelo servidor.
 */
export function EffectSummary({ effect, applied = false, caption }: {
  effect?: ProposalEffect | null;
  applied?: boolean;
  caption: string;
}) {
  if (!effect) return <p className="ai-muted">O servidor não informou o efeito.</p>;
  const hasSnapshot = !!(effect.before || effect.after);
  const pairs = [...effectCounts(effect, applied), ...effectTotals(effect)];

  return <div className="ai-effect">
    {effect.state_after && <p className="ai-effect-state">
      <span className="ai-muted">{applied ? 'Estado gravado:' : 'Estado depois de aplicar:'}</span> <LedgerStateBadge state={effect.state_after} />
    </p>}
    {hasSnapshot && <table className="ai-table">
      <caption>{caption}</caption>
      <thead><tr><th scope="col"><span className="ai-sr-only">Campo</span></th><th scope="col">Antes</th><th scope="col">{applied ? 'Gravado' : 'Depois'}</th></tr></thead>
      <tbody>
        <tr><th scope="row">Pago</th><td>{money(effect.before?.paid)}</td><td>{money(effect.after?.paid)}</td></tr>
        <tr><th scope="row">Restante</th><td>{money(effect.before?.remaining)}</td><td>{money(effect.after?.remaining)}</td></tr>
        <tr><th scope="row">Situação</th><td>{payableStatusLabel(effect.before?.status)}</td><td>{payableStatusLabel(effect.after?.status)}</td></tr>
      </tbody>
    </table>}
    {pairs.length > 0 && <dl className="ai-pairs">
      {pairs.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{breakable(value)}</dd></div>)}
    </dl>}
    {!hasSnapshot && pairs.length === 0 && !effect.state_after && <p className="ai-muted">O servidor não informou o efeito.</p>}
  </div>;
}
