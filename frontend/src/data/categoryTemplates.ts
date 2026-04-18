/**
 * Catálogo local de modelos para assistência na criação de categorias.
 * Evolução futura: pode ser carregado de API ou tabela auxiliar sem mudar a UI.
 */

export type CategoryKind = 'expense' | 'income';

export interface CategoryTemplate {
  /** Chave estável (ex.: moradia) */
  id: string;
  /** Nome principal exibido nas sugestões */
  label: string;
  /** Valores sugeridos para o campo Nome (único por template; inclui o label quando fizer sentido) */
  nameSuggestions: string[];
  /** Exemplos curtos para inspiração (subitens, fornecedores, etc.) */
  relatedExampleTags: string[];
  /** Frases opcionais de contexto */
  relatedExampleHints?: string[];
  /** Preenchimento opcional ao escolher uma sugestão deste modelo (somente criação) */
  icon?: string;
  color?: string;
  descriptionHint?: string;
}

export const CATEGORY_TEMPLATES: Record<CategoryKind, readonly CategoryTemplate[]> = {
  expense: [
    {
      id: 'moradia',
      label: 'Moradia',
      nameSuggestions: [
        'Moradia',
        'Aluguel',
        'Condomínio',
        'Energia',
        'Água',
        'Internet',
        'Gás',
      ],
      relatedExampleTags: ['aluguel', 'condomínio', 'energia', 'água', 'internet', 'IPTU condomínio'],
      relatedExampleHints: ['Conta fixa mensal', 'Despesa essencial da casa', 'Serviço recorrente'],
      icon: 'house',
      color: '#6366f1',
      descriptionHint: 'Despesas fixas e variáveis da residência.',
    },
    {
      id: 'educacao',
      label: 'Educação',
      nameSuggestions: [
        'Educação',
        'Escola',
        'Ballet',
        'Curso',
        'Material Escolar',
        'Transporte Escolar',
      ],
      relatedExampleTags: ['escola', 'ballet', 'curso', 'material escolar', 'transporte escolar', 'mensalidade'],
      relatedExampleHints: ['Mensalidade', 'Atividade infantil', 'Despesa educacional'],
      icon: 'trophy',
      color: '#8b5cf6',
      descriptionHint: 'Investimento em estudo e desenvolvimento.',
    },
    {
      id: 'cartoes',
      label: 'Cartões',
      nameSuggestions: ['Cartões', 'Nubank', 'Renner', 'Will Bank', 'Riachuelo', 'Mercado Pago'],
      relatedExampleTags: ['nubank', 'renner', 'will bank', 'riachuelo', 'mercado pago', 'fatura'],
      relatedExampleHints: ['Fatura mensal', 'Cartão de loja', 'Crédito parcelado'],
      icon: 'credit-card',
      color: '#ec4899',
      descriptionHint: 'Pagamentos e faturas de cartão.',
    },
    {
      id: 'transporte',
      label: 'Transporte',
      nameSuggestions: [
        'Transporte',
        'Combustível',
        'Uber',
        'Manutenção',
        'Estacionamento',
        'IPVA',
        'Seguro auto',
      ],
      relatedExampleTags: ['combustível', 'uber', 'manutenção', 'estacionamento', 'pedágio', 'licenciamento'],
      relatedExampleHints: ['Despesa com veículo', 'Despesa de locomoção'],
      icon: 'car-front',
      color: '#f59e0b',
      descriptionHint: 'Locomoção e custos do veículo.',
    },
    {
      id: 'saude',
      label: 'Saúde',
      nameSuggestions: ['Saúde', 'Farmácia', 'Consulta', 'Psicólogo', 'Terapia', 'Plano de Saúde'],
      relatedExampleTags: ['farmácia', 'consulta', 'exames', 'plano', 'dentista', 'fisioterapia'],
      relatedExampleHints: ['Cuidado pessoal', 'Despesa médica', 'Bem-estar'],
      icon: 'heart-pulse',
      color: '#ef4444',
      descriptionHint: 'Cuidados com saúde e bem-estar.',
    },
    {
      id: 'alimentacao',
      label: 'Alimentação',
      nameSuggestions: ['Alimentação', 'Supermercado', 'Padaria', 'Lanche', 'Restaurante', 'Delivery'],
      relatedExampleTags: ['supermercado', 'feira', 'ifood', 'restaurante', 'café'],
      relatedExampleHints: ['Consumo doméstico', 'Alimentação fora de casa'],
      icon: 'basket',
      color: '#10b981',
      descriptionHint: 'Compras de mercado e refeições.',
    },
    {
      id: 'servicos',
      label: 'Serviços',
      nameSuggestions: ['Serviços', 'Faxineira', 'Manutenção', 'Lavanderia', 'Babá', 'Técnico'],
      relatedExampleTags: ['faxineira', 'encanador', 'eletricista', 'lavanderia', 'babá'],
      relatedExampleHints: ['Serviço terceirizado', 'Pagamento recorrente ou avulso'],
      icon: 'tools',
      color: '#06b6d4',
      descriptionHint: 'Serviços contratados para casa ou trabalho.',
    },
    {
      id: 'impostos',
      label: 'Impostos',
      nameSuggestions: ['Impostos', 'IPVA', 'IPTU', 'Taxa', 'Licenciamento'],
      relatedExampleTags: ['IPVA', 'IPTU', 'DARF', 'taxas municipais', 'licenciamento'],
      relatedExampleHints: ['Obrigação fiscal', 'Despesa anual ou periódica'],
      icon: 'bank',
      color: '#64748b',
      descriptionHint: 'Tributos e taxas obrigatórias.',
    },
    {
      id: 'pessoal',
      label: 'Pessoal',
      nameSuggestions: ['Pessoal', 'Roupas', 'Beleza', 'Lazer', 'Assinaturas', 'Presentes'],
      relatedExampleTags: ['roupas', 'cabeleireiro', 'streaming', 'cinema', 'presentes'],
      relatedExampleHints: ['Consumo pessoal', 'Despesa não essencial'],
      icon: 'bag',
      color: '#f97316',
      descriptionHint: 'Gastos pessoais e entretenimento.',
    },
  ],
  income: [
    {
      id: 'salario',
      label: 'Salário',
      nameSuggestions: ['Salário', 'Adiantamento', 'Férias', '13º'],
      relatedExampleTags: ['folha', 'CLT', 'holerite', 'adiantamento quinzenal'],
      relatedExampleHints: ['Receita principal', 'Pagamento empregatício'],
      icon: 'briefcase',
      color: '#10b981',
      descriptionHint: 'Rendimentos do vínculo empregatício.',
    },
    {
      id: 'extra',
      label: 'Renda Extra',
      nameSuggestions: ['Renda Extra', 'Freelance', 'Venda', 'Comissão', 'Reembolso', 'Pix recebido'],
      relatedExampleTags: ['freelance', 'bico', 'venda OLX', 'comissão', 'reembolso'],
      relatedExampleHints: ['Receita complementar', 'Entrada eventual'],
      icon: 'cash-coin',
      color: '#22c55e',
      descriptionHint: 'Entradas fora do salário fixo.',
    },
    {
      id: 'investimentos',
      label: 'Investimentos',
      nameSuggestions: ['Investimentos', 'Rendimento', 'Resgate', 'Dividendos', 'Juros'],
      relatedExampleTags: ['CDB', 'Tesouro', 'dividendos', 'FIIs', 'resgate'],
      relatedExampleHints: ['Receita financeira', 'Rentabilidade'],
      icon: 'graph-up-arrow',
      color: '#3b82f6',
      descriptionHint: 'Ganhos com aplicações e investimentos.',
    },
  ],
} as const;
