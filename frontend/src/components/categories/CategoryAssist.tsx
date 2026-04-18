import React, { useId } from 'react';
import type { CategoryKind } from '../../data/categoryTemplates';
import {
  filterNameSuggestions,
  getRelatedExamples,
  normalizeCategoryText,
} from '../../utils/categoryAssist';

export type CategoryNameSuggestionsProps = {
  kind: CategoryKind;
  /** Texto atual do nome (filtra sugestões) */
  nameQuery: string;
  /** Valor do campo nome (destaque do chip selecionado) */
  currentName: string;
  disabled?: boolean;
  onSelect: (text: string) => void;
  className?: string;
};

/**
 * Chips roláveis de sugestões para o campo Nome (somente assistivo).
 */
export const CategoryNameSuggestions: React.FC<CategoryNameSuggestionsProps> = ({
  kind,
  nameQuery,
  currentName,
  disabled,
  onSelect,
  className = '',
}) => {
  const uid = useId();
  const headingId = `${uid}-suggestions-heading`;
  const listId = `${uid}-suggestions-list`;
  const items = filterNameSuggestions(kind, nameQuery);
  const currentNorm = normalizeCategoryText(currentName);

  return (
    <section
      className={`rounded-lg border border-slate-200/90 bg-slate-50/50 dark:border-slate-600/35 dark:bg-[#252836]/40 ${className}`}
      aria-labelledby={headingId}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200/70 px-3 py-2 dark:border-slate-600/30">
        <div className="flex items-center gap-2">
          <h6 id={headingId} className="mb-0 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Sugestões
          </h6>
          <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-700/80 dark:text-slate-400">
            opcional
          </span>
        </div>
        <p className="mb-0 text-[11px] text-slate-500 dark:text-slate-400">Clique para preencher o nome — continua editável.</p>
      </div>
      <div
        id={listId}
        role="group"
        aria-label="Sugestões de nome para a categoria"
        className="max-h-[7.25rem] overflow-y-auto scroll-smooth overscroll-contain px-3 py-2.5"
      >
        {items.length === 0 ? (
          <p className="mb-0 text-sm text-slate-500 dark:text-slate-400" role="status">
            Nenhuma sugestão para esse trecho. Você pode seguir digitando qualquer nome.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {items.map(({ text, template }) => {
              const active = normalizeCategoryText(text) === currentNorm;
              return (
                <button
                  key={`${template.id}-${text}`}
                  type="button"
                  aria-current={active ? 'true' : undefined}
                  disabled={disabled}
                  onClick={() => onSelect(text)}
                  title={`Usar “${text}” como nome`}
                  className={[
                    'category-name-suggestion inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-left text-xs font-medium transition-all duration-150',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-100 dark:focus-visible:ring-offset-[#1a1d29]',
                    active
                      ? 'border-brand-500 bg-brand-100/90 text-brand-800 shadow-sm ring-1 ring-brand-500/40 dark:border-brand-500/70 dark:!bg-brand-500/20 dark:!text-brand-100 dark:ring-brand-400/35'
                      : [
                          'border-slate-300 bg-slate-100 text-slate-800',
                          'hover:border-brand-400/60 hover:bg-slate-200/90',
                          'dark:border-slate-500 dark:!bg-[#252836] dark:!text-slate-200',
                          'dark:hover:border-slate-400 dark:hover:!bg-[#2d3142]',
                        ].join(' '),
                    disabled ? 'pointer-events-none opacity-50' : '',
                  ].join(' ')}
                >
                  <span className="truncate">{text}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};

export type CategoryRelatedExamplesProps = {
  kind: CategoryKind;
  currentName: string;
  disabled?: boolean;
  /** Clique opcional: ex. acrescentar à descrição */
  onExampleTagClick?: (tag: string) => void;
  className?: string;
};

/**
 * Exemplos contextuais (tags + dicas) conforme tipo e nome.
 */
export const CategoryRelatedExamples: React.FC<CategoryRelatedExamplesProps> = ({
  kind,
  currentName,
  disabled,
  onExampleTagClick,
  className = '',
}) => {
  const uid = useId();
  const headingId = `${uid}-examples-heading`;
  const payload = getRelatedExamples(kind, currentName);
  const animKey = `${kind}-${payload.templateId ?? 'fallback'}-${normalizeCategoryText(currentName).slice(0, 24)}`;

  return (
    <section
      className={`rounded-lg border border-slate-200/90 bg-slate-50/50 dark:border-slate-600/35 dark:bg-[#252836]/40 ${className}`}
      aria-labelledby={headingId}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200/70 px-3 py-2 dark:border-slate-600/30">
        <div className="flex items-center gap-2">
          <h6 id={headingId} className="mb-0 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Exemplos relacionados
          </h6>
          <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-700/80 dark:text-slate-400">
            inspiração
          </span>
        </div>
      </div>
      <div
        key={animKey}
        className="space-y-2.5 px-3 py-2.5 animate-fade-in"
      >
        {payload.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {payload.tags.map((tag) => {
              const interactive = Boolean(onExampleTagClick) && !disabled;
              if (interactive) {
                return (
                  <button
                    key={tag}
                    type="button"
                    disabled={disabled}
                    onClick={() => onExampleTagClick?.(tag)}
                    title="Adicionar à descrição (se ainda não estiver lá)"
                    className="cursor-pointer rounded-md border border-dashed border-slate-300 bg-white/90 px-2 py-0.5 text-[11px] text-slate-600 transition-colors hover:border-brand-400 hover:bg-brand-500/5 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 dark:border-slate-500 dark:bg-[#1a1d29]/90 dark:text-slate-300 dark:hover:border-brand-500/50 dark:hover:text-brand-200"
                  >
                    {tag}
                  </button>
                );
              }
              return (
                <span
                  key={tag}
                  className="rounded-md border border-dashed border-slate-200/90 bg-white/60 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-600/50 dark:bg-transparent dark:text-slate-400"
                >
                  {tag}
                </span>
              );
            })}
          </div>
        )}
        {payload.hints.length > 0 && (
          <ul className="mb-0 list-disc space-y-1 pl-4 text-[11px] leading-snug text-slate-500 dark:text-slate-400">
            {payload.hints.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        )}
        {payload.tags.length === 0 && payload.hints.length === 0 && (
          <p className="mb-0 text-sm text-slate-500 dark:text-slate-400" role="status">
            Digite ou escolha um nome para ver exemplos nesta categoria.
          </p>
        )}
      </div>
    </section>
  );
};
