import { CATEGORY_TEMPLATES, type CategoryKind, type CategoryTemplate } from '../data/categoryTemplates';

/** Remove marcas diacríticas após NFD (amplamente suportado). */
const COMBINING_MARKS = /[\u0300-\u036f]/g;

export function normalizeCategoryText(value: string): string {
  return value
    .normalize('NFD')
    .replace(COMBINING_MARKS, '')
    .toLowerCase()
    .trim();
}

export interface FlatNameSuggestion {
  text: string;
  template: CategoryTemplate;
}

/** Lista achatada de sugestões de nome com deduplicação (preserva ordem do catálogo). */
export function listFlatNameSuggestions(kind: CategoryKind): FlatNameSuggestion[] {
  const seen = new Set<string>();
  const out: FlatNameSuggestion[] = [];
  for (const template of CATEGORY_TEMPLATES[kind]) {
    for (const text of template.nameSuggestions) {
      const key = normalizeCategoryText(text);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push({ text, template });
    }
  }
  return out;
}

function scoreNameMatch(queryNorm: string, text: string): number {
  const tn = normalizeCategoryText(text);
  if (!queryNorm) return 0;
  if (tn === queryNorm) return 100;
  if (tn.startsWith(queryNorm)) return 80;
  if (tn.includes(queryNorm)) return 60;
  const words = tn.split(/\s+/);
  if (words.some((w) => w.startsWith(queryNorm))) return 50;
  return 0;
}

/**
 * Filtra e ordena sugestões conforme o texto digitado (assistivo, não restritivo).
 */
export function filterNameSuggestions(
  kind: CategoryKind,
  nameQuery: string,
  max = 48,
): FlatNameSuggestion[] {
  const flat = listFlatNameSuggestions(kind);
  const q = normalizeCategoryText(nameQuery);
  if (!q) {
    return flat.slice(0, max);
  }
  const scored = flat
    .map((item) => ({ item, score: scoreNameMatch(q, item.text) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || a.item.text.localeCompare(b.item.text, 'pt-BR'));
  if (scored.length === 0) {
    return [];
  }
  return scored.slice(0, max).map((s) => s.item);
}

/**
 * Resolve o modelo mais relevante para o nome atual (exemplos relacionados).
 */
export function resolveTemplateForName(kind: CategoryKind, rawName: string): CategoryTemplate | null {
  const n = normalizeCategoryText(rawName);
  if (!n) return null;
  const list = CATEGORY_TEMPLATES[kind];

  const byLabel = list.find((t) => normalizeCategoryText(t.label) === n);
  if (byLabel) return byLabel;

  const bySuggestion = list.find((t) =>
    t.nameSuggestions.some((s) => normalizeCategoryText(s) === n),
  );
  if (bySuggestion) return bySuggestion;

  if (n.length >= 2) {
    let best: { template: CategoryTemplate; score: number } | null = null;
    for (const t of list) {
      const ln = normalizeCategoryText(t.label);
      let score = 0;
      if (ln.startsWith(n) || n.startsWith(ln)) score = 70;
      else if (ln.includes(n) || n.includes(ln)) score = 40;
      if (score > 0 && (!best || score > best.score)) {
        best = { template: t, score };
      }
    }
    if (best) return best.template;
  }

  return null;
}

export interface RelatedExamplesPayload {
  tags: string[];
  hints: string[];
  templateId: string | null;
}

const FALLBACK: Record<CategoryKind, RelatedExamplesPayload> = {
  expense: {
    tags: ['contas do mês', 'assinaturas', 'compras recorrentes', 'imprevistos'],
    hints: ['Use nomes que faça sentido para você no dia a dia.'],
    templateId: null,
  },
  income: {
    tags: ['salário', 'extras', 'reembolsos', 'rendimentos'],
    hints: ['Separe a receita principal das entradas eventuais, se ajudar.'],
    templateId: null,
  },
};

export function getRelatedExamples(kind: CategoryKind, rawName: string): RelatedExamplesPayload {
  const template = resolveTemplateForName(kind, rawName);
  if (!template) {
    return FALLBACK[kind];
  }
  return {
    tags: [...template.relatedExampleTags],
    hints: template.relatedExampleHints ? [...template.relatedExampleHints] : [],
    templateId: template.id,
  };
}

/** Localiza o template associado a um texto de sugestão clicado (para preencher ícone/cor). */
export function getTemplateForSuggestionText(kind: CategoryKind, suggestionText: string): CategoryTemplate | null {
  const n = normalizeCategoryText(suggestionText);
  if (!n) return null;
  for (const t of CATEGORY_TEMPLATES[kind]) {
    if (t.nameSuggestions.some((s) => normalizeCategoryText(s) === n)) {
      return t;
    }
  }
  return null;
}
