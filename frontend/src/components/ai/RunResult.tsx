import { TriangleAlert } from 'lucide-react';
import { Code } from './AiBits';
import { formatFactValue, formatInstant, formatPeriod, sourceKindLabel, spaceKindLabel, warningText } from './aiFormat';
import type { AiRun, Fact, Source } from './aiTypes';

function FactCard({ fact, sources }: { fact: Fact; sources: Map<string, Source> }) {
  const display = formatFactValue(fact);
  const period = formatPeriod(fact.period);
  const scope = [fact.scope?.kind ? spaceKindLabel(fact.scope.kind) : null, fact.scope?.declared || null].filter(Boolean).join(' · ');
  const asOf = formatInstant(fact.as_of);
  const refs = fact.source_refs ?? [];

  return <li className="ai-fact">
    <h3>{fact.label}</h3>
    <p className={`ai-fact-value ${display.missing ? 'ai-fact-missing' : ''}`}>{display.text}</p>
    {/* Sem valor: travessão e o motivo. Zero aqui seria afirmar um saldo que ninguém calculou. */}
    {display.missing && <p className="ai-fact-reason">Sem valor: {display.missing}</p>}
    <dl className="ai-pairs ai-pairs-compact">
      <div><dt>Período</dt><dd>{period ?? 'Não informado'}</dd></div>
      <div><dt>Escopo</dt><dd>{scope || 'Não informado'}</dd></div>
      <div><dt>De onde veio</dt><dd>
        {refs.length === 0
          ? 'Fonte não informada'
          : <ul className="ai-plain-list">{refs.map(ref => <li key={ref}>{sources.get(ref)?.label ?? <Code>{ref}</Code>}</li>)}</ul>}
      </dd></div>
      {asOf && <div><dt>Calculado em</dt><dd>{asOf}</dd></div>}
    </dl>
  </li>;
}

/**
 * Resultado de uma execução: resumo, fatos e fontes.
 *
 * Os números são os fatos calculados pelo backend (cada um com período, escopo
 * e fonte). O texto do resumo é do modelo e pode errar; por isso os fatos ficam
 * em destaque e sempre dizem de onde vieram.
 */
export function RunResult({ run }: { run: AiRun }) {
  const facts = run.facts ?? [];
  const sourceList = run.sources ?? [];
  const sources = new Map(sourceList.map(source => [source.ref, source] as const));
  const warnings = (run.warnings ?? []).map(warningText).filter((text): text is string => !!text);
  const fallback = run.model?.fallback_used === true;

  return <div className="ai-stack">
    {(fallback || warnings.length > 0) && <div className="ai-warning" role="note">
      <p className="ai-warning-title"><TriangleAlert size={18} aria-hidden="true" />Atenção ao conferir</p>
      {fallback && <p>O modelo preferido não respondeu, então esta resposta foi preparada por um modelo alternativo{run.model?.alias ? ` (${run.model.alias})` : ''}. Os valores continuam vindo dos dados do aplicativo; leia o texto com mais atenção.</p>}
      {warnings.length > 0 && <ul className="ai-plain-list">{warnings.map(text => <li key={text}>{text}</li>)}</ul>}
    </div>}

    {run.summary_pt_br && <p className="ai-summary">{run.summary_pt_br}</p>}

    {facts.length > 0 && <ul className="ai-facts" aria-label="Fatos calculados">
      {facts.map(fact => <FactCard key={fact.key} fact={fact} sources={sources} />)}
    </ul>}

    {sourceList.length > 0 && <div className="ai-block">
      <h3>Fontes</h3>
      <ul className="ai-sources">
        {sourceList.map(source => {
          const asOf = formatInstant(source.as_of);
          return <li key={source.ref}>
            <span className="ai-source-label">{source.label}</span>
            <span className="ai-muted ai-small">{sourceKindLabel(source.kind)}{asOf ? ` · consultado em ${asOf}` : ''}</span>
            <Code>{source.ref}</Code>
          </li>;
        })}
      </ul>
    </div>}
  </div>;
}
