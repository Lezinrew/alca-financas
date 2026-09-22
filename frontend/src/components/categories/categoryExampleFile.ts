export const availableIcons = [
  'circle', 'basket', 'car-front', 'house', 'heart-pulse', 'currency-dollar',
  'briefcase', 'phone', 'wifi', 'lightning', 'fuel-pump', 'bag',
  'cart', 'cup-straw', 'trophy', 'gift', 'airplane', 'bicycle',
  'bus-front', 'train-front', 'bank', 'credit-card', 'piggy-bank',
  'cash-coin', 'graph-up-arrow', 'tools', 'hammer', 'wrench',
];

export const availableColors = [
  '#6366f1', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6b7280',
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
  '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43',
];

const exampleIncomeCategories = [
  { name: 'Salário', type: 'income', color: '#10b981', icon: 'currency-dollar', description: 'Salário mensal' },
  { name: 'Freelance', type: 'income', color: '#3b82f6', icon: 'briefcase', description: 'Trabalhos freelancer' },
  { name: 'Investimentos', type: 'income', color: '#f59e0b', icon: 'graph-up-arrow', description: 'Rendimentos de investimentos' },
  { name: 'Renda Extra', type: 'income', color: '#8b5cf6', icon: 'lightning', description: 'Renda extra ocasional' },
  { name: 'Aluguel', type: 'income', color: '#06b6d4', icon: 'house', description: 'Receita de aluguel' },
  { name: 'Vendas', type: 'income', color: '#84cc16', icon: 'cart', description: 'Vendas de produtos' },
  { name: 'Presentes', type: 'income', color: '#ec4899', icon: 'gift', description: 'Presentes recebidos' },
  { name: 'Reembolso', type: 'income', color: '#4ECDC4', icon: 'cash-coin', description: 'Reembolsos diversos' },
];

const exampleExpenseCategories = [
  { name: 'Alimentação', type: 'expense', color: '#FF6B6B', icon: 'basket', description: 'Gastos com comida e bebida' },
  { name: 'Transporte', type: 'expense', color: '#4ECDC4', icon: 'car-front', description: 'Combustível, transporte público, etc' },
  { name: 'Moradia', type: 'expense', color: '#45B7D1', icon: 'house', description: 'Aluguel, condomínio, IPTU' },
  { name: 'Saúde', type: 'expense', color: '#96CEB4', icon: 'heart-pulse', description: 'Médico, remédios, plano de saúde' },
  { name: 'Educação', type: 'expense', color: '#9B59B6', icon: 'briefcase', description: 'Cursos, livros, mensalidades' },
  { name: 'Lazer', type: 'expense', color: '#F39C12', icon: 'trophy', description: 'Cinema, shows, entretenimento' },
  { name: 'Vestuário', type: 'expense', color: '#E74C3C', icon: 'bag', description: 'Roupas, calçados, acessórios' },
  { name: 'Utilidades', type: 'expense', color: '#FECA57', icon: 'lightning', description: 'Luz, água, gás, internet' },
  { name: 'Assinaturas', type: 'expense', color: '#6366f1', icon: 'credit-card', description: 'Netflix, Spotify, etc' },
  { name: 'Serviços', type: 'expense', color: '#95A5A6', icon: 'tools', description: 'Manutenção, reparos, serviços' },
  { name: 'Doações', type: 'expense', color: '#E67E22', icon: 'heart-pulse', description: 'Doações e caridade' },
  { name: 'Cuidados Pessoais', type: 'expense', color: '#FF9FF3', icon: 'circle', description: 'Salão, produtos de beleza' },
  { name: 'Pets', type: 'expense', color: '#54A0FF', icon: 'circle', description: 'Ração, veterinário, pet shop' },
  { name: 'Impostos', type: 'expense', color: '#6b7280', icon: 'bank', description: 'Impostos e taxas' },
  { name: 'Empréstimos', type: 'expense', color: '#ef4444', icon: 'cash-coin', description: 'Parcelas de empréstimos' },
];

export function buildCategoryExampleFile() {
  return {
    info: {
      description: 'Arquivo de exemplo para importação de categorias',
      version: '1.0',
      created_at: new Date().toISOString(),
      instructions: [
        'Este arquivo contém exemplos de categorias com diferentes ícones e cores disponíveis.',
        'Você pode usar este arquivo como modelo para criar suas próprias categorias.',
        'Edite os campos conforme necessário e importe usando o botão "Importar Categorias" nas Configurações.',
        '',
        'Campos obrigatórios:',
        '  - name: Nome da categoria',
        '  - type: "income" (receita) ou "expense" (despesa)',
        '',
        'Campos opcionais:',
        '  - color: Cor em formato hexadecimal (ex: #FF6B6B)',
        '  - icon: Nome do ícone Bootstrap Icons (sem o prefixo "bi-")',
        '  - description: Descrição da categoria',
        '',
        'Ícones disponíveis:',
        ...availableIcons.map(icon => `  - ${icon}`),
        '',
        'Cores disponíveis:',
        ...availableColors.map(color => `  - ${color}`),
      ],
    },
    categories: [...exampleIncomeCategories, ...exampleExpenseCategories],
    available_icons: availableIcons,
    available_colors: availableColors,
  };
}

/** Gera e baixa o JSON de exemplo no navegador. */
export function downloadCategoryExampleFile() {
  const blob = new Blob([JSON.stringify(buildCategoryExampleFile(), null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `categorias-exemplo-${new Date().toISOString().split('T')[0]}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
