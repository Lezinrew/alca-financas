import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { categoriesAPI } from '../../utils/api';
import CategoryForm from './CategoryForm';

type CategoryType = 'income' | 'expense';

interface Category {
  id: string;
  name: string;
  type: CategoryType;
  color: string;
  icon: string;
  description?: string;
}

type CategoryPayload = {
  name: string;
  type: CategoryType;
  color: string;
  icon: string;
  description?: string;
};

const Categories = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  useEffect(() => {
    // Só carrega dados se o usuário estiver autenticado e a autenticação não estiver carregando
    if (isAuthenticated && !authLoading) {
      loadCategories();
    }
  }, [isAuthenticated, authLoading]);

  const loadCategories = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await categoriesAPI.getAll();
      setCategories(response.data as Category[]);
    } catch (err) {
      setError('Erro ao carregar categorias');
      console.error('Load categories error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCategory = () => {
    setEditingCategory(null);
    setShowForm(true);
  };

  const handleEditCategory = (category: Category) => {
    console.log('Categories: handleEditCategory chamado para:', category.id);
    setEditingCategory(category);
    setShowForm(true);
  };

  const handleDeleteCategory = async (categoryId: string) => {
    console.log('Categories: handleDeleteCategory chamado para:', categoryId);

    if (!window.confirm('Tem certeza que deseja excluir esta categoria? Esta ação não pode ser desfeita.')) {
      return;
    }

    try {
      setLoading(true);
      setError('');
      console.log('Deletando categoria:', categoryId);

      await categoriesAPI.delete(categoryId);
      console.log('Categoria deletada com sucesso');

      // Recarrega a lista de categorias
      await loadCategories();

      // Mostra mensagem de sucesso temporária
      setSuccess('Categoria excluída com sucesso!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      console.error('Delete category error:', err);
      const errorMessage = err.response?.data?.error || err.response?.data?.message || 'Erro ao deletar categoria';
      setError(errorMessage);

      // Remove a mensagem de erro após 5 segundos
      setTimeout(() => setError(''), 5000);
    } finally {
      setLoading(false);
    }
  };

  // Fecha o menu ao clicar fora
  useEffect(() => {
    if (!openMenuId) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;

      // Não fecha se o clique foi dentro do menu dropdown ou no botão do menu
      const clickedInsideMenu = target.closest('.dropdown-menu');
      const clickedOnMenuButton = target.closest('.category-menu');
      const clickedOnDropdownItem = target.closest('.dropdown-item');

      if (clickedInsideMenu || clickedOnMenuButton || clickedOnDropdownItem) {
        return;
      }

      // Fecha o menu se o clique foi fora
      setOpenMenuId(null);
    };

    // Adiciona o listener no próximo tick para não interferir com o clique do botão
    const timeoutId = setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('click', handleClickOutside);
    };
  }, [openMenuId]);

  const handleFormSubmit = async (formData: CategoryPayload) => {
    try {
      if (editingCategory) {
        await categoriesAPI.update(editingCategory.id, formData);
      } else {
        await categoriesAPI.create(formData);
      }

      setShowForm(false);
      setEditingCategory(null);
      await loadCategories();
    } catch (err) {
      throw err;
    }
  };

  const handleExportExample = () => {
    // Lista de ícones disponíveis
    const availableIcons = [
      'circle', 'basket', 'car-front', 'house', 'heart-pulse', 'currency-dollar',
      'briefcase', 'phone', 'wifi', 'lightning', 'fuel-pump', 'bag',
      'cart', 'cup-straw', 'trophy', 'gift', 'airplane', 'bicycle',
      'bus-front', 'train-front', 'bank', 'credit-card', 'piggy-bank',
      'cash-coin', 'graph-up-arrow', 'tools', 'hammer', 'wrench'
    ];

    // Lista de cores disponíveis
    const availableColors = [
      '#6366f1', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
      '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6b7280',
      '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
      '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43'
    ];

    // Categorias de exemplo - Receitas
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

    // Categorias de exemplo - Despesas
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

    // Arquivo de exemplo completo
    const exampleFile = {
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
          ...availableColors.map(color => `  - ${color}`)
        ]
      },
      categories: [
        ...exampleIncomeCategories,
        ...exampleExpenseCategories
      ],
      available_icons: availableIcons,
      available_colors: availableColors
    };

    // Cria o blob e faz download
    const blob = new Blob([JSON.stringify(exampleFile, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `categorias-exemplo-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setSuccess('Arquivo de exemplo baixado com sucesso!');
    setTimeout(() => setSuccess(''), 3000);
  };

  // Mostra loading enquanto autenticação está sendo verificada ou dados estão carregando
  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-slate-600">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  const incomeCategories = categories.filter(cat => cat.type === 'income');
  const expenseCategories = categories.filter(cat => cat.type === 'expense');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Categorias</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Organize suas receitas e despesas</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleExportExample}
            className="px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
            title="Baixar arquivo de exemplo com categorias, ícones e cores disponíveis"
          >
            <i className="bi bi-file-earmark-arrow-down"></i>
            Baixar Exemplo
          </button>
          <button
            onClick={handleAddCategory}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
          >
            <i className="bi bi-plus-circle"></i>
            Nova Categoria
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2 transition-colors">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
          <span className="text-red-700 dark:text-red-300">{error}</span>
        </div>
      )}

      {success && (
        <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4 flex items-center gap-2 transition-colors">
          <i className="bi bi-check-circle-fill text-emerald-600 dark:text-emerald-400"></i>
          <span className="text-emerald-700 dark:text-emerald-300">{success}</span>
        </div>
      )}

      {/* Income Categories */}
      <div className="card-base">
        <div className="bg-emerald-50 dark:bg-emerald-900/20 border-b border-emerald-100 dark:border-emerald-800/50 px-6 py-4 transition-colors">
          <div className="flex items-center gap-2">
            <i className="bi bi-arrow-up-circle text-emerald-600"></i>
            <h2 className="text-lg font-semibold text-emerald-900 dark:text-emerald-300">Receitas</h2>
            <span className="ml-auto text-sm text-emerald-700 dark:text-emerald-400">{incomeCategories.length} categorias</span>
          </div>
        </div>
        <div className="p-6">
          {incomeCategories.length === 0 ? (
            <p className="text-center text-slate-500 dark:text-slate-400 py-8">Nenhuma categoria de receita cadastrada</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {incomeCategories.map((category) => (
                <div
                  key={category.id}
                  className="card-elevated flex items-center justify-between p-4 hover:border-slate-300 dark:hover:border-slate-600 hover:shadow-sm group relative"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: category.color }}
                    >
                      <i className={`bi bi-${category.icon} text-white`}></i>
                    </div>
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{category.name}</p>
                      {category.description && (
                        <p className="text-xs text-slate-500 dark:text-slate-400">{category.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="relative category-menu">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Categories: Botão menu clicado, openMenuId atual:', openMenuId, 'category.id:', category.id);
                        setOpenMenuId(openMenuId === category.id ? null : category.id);
                      }}
                      className="p-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors opacity-60 group-hover:opacity-100"
                      aria-label="Opções da categoria"
                    >
                      <i className="bi bi-three-dots-vertical text-sm"></i>
                    </button>

                    {openMenuId === category.id && (
                      <div className="dropdown-menu absolute right-0 top-full mt-1 w-40 py-1" style={{ zIndex: 9999, position: 'absolute' }}>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Categories: Botão editar clicado para categoria:', category.id);
                            setOpenMenuId(null);
                            // Usa setTimeout para garantir que o menu seja fechado antes de chamar handleEditCategory
                            setTimeout(() => {
                              handleEditCategory(category);
                            }, 0);
                          }}
                          className="dropdown-item w-full text-left px-4 py-2 text-sm flex items-center gap-2"
                        >
                          <i className="bi bi-pencil text-blue-600 dark:text-blue-400"></i>
                          <span>Editar</span>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Categories: Botão excluir clicado para categoria:', category.id);
                            setOpenMenuId(null);
                            // Usa setTimeout para garantir que o menu seja fechado antes de chamar handleDeleteCategory
                            setTimeout(() => {
                              handleDeleteCategory(category.id);
                            }, 0);
                          }}
                          className="dropdown-item w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                        >
                          <i className="bi bi-trash"></i>
                          <span>Excluir</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Expense Categories */}
      <div className="card-base">
        <div className="bg-red-50 dark:bg-red-900/20 border-b border-red-100 dark:border-red-800/50 px-6 py-4">
          <div className="flex items-center gap-2">
            <i className="bi bi-arrow-down-circle text-red-600"></i>
            <h2 className="text-lg font-semibold text-red-900 dark:text-red-300">Despesas</h2>
            <span className="ml-auto text-sm text-red-700 dark:text-red-400">{expenseCategories.length} categorias</span>
          </div>
        </div>
        <div className="p-6">
          {expenseCategories.length === 0 ? (
            <p className="text-center text-slate-500 dark:text-slate-400 py-8">Nenhuma categoria de despesa cadastrada</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {expenseCategories.map((category) => (
                <div
                  key={category.id}
                  className="card-elevated flex items-center justify-between p-4 hover:border-slate-300 dark:hover:border-slate-600 hover:shadow-sm group relative"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: category.color }}
                    >
                      <i className={`bi bi-${category.icon} text-white`}></i>
                    </div>
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{category.name}</p>
                      {category.description && (
                        <p className="text-xs text-slate-500 dark:text-slate-400">{category.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="relative category-menu">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Categories: Botão menu clicado, openMenuId atual:', openMenuId, 'category.id:', category.id);
                        setOpenMenuId(openMenuId === category.id ? null : category.id);
                      }}
                      className="p-1.5 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors opacity-60 group-hover:opacity-100"
                      aria-label="Opções da categoria"
                    >
                      <i className="bi bi-three-dots-vertical text-sm"></i>
                    </button>

                    {openMenuId === category.id && (
                      <div className="dropdown-menu absolute right-0 top-full mt-1 w-40 py-1" style={{ zIndex: 9999, position: 'absolute' }}>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Categories: Botão editar clicado para categoria:', category.id);
                            setOpenMenuId(null);
                            // Usa setTimeout para garantir que o menu seja fechado antes de chamar handleEditCategory
                            setTimeout(() => {
                              handleEditCategory(category);
                            }, 0);
                          }}
                          className="dropdown-item w-full text-left px-4 py-2 text-sm flex items-center gap-2"
                        >
                          <i className="bi bi-pencil text-blue-600 dark:text-blue-400"></i>
                          <span>Editar</span>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Categories: Botão excluir clicado para categoria:', category.id);
                            setOpenMenuId(null);
                            // Usa setTimeout para garantir que o menu seja fechado antes de chamar handleDeleteCategory
                            setTimeout(() => {
                              handleDeleteCategory(category.id);
                            }, 0);
                          }}
                          className="dropdown-item w-full text-left px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
                        >
                          <i className="bi bi-trash"></i>
                          <span>Excluir</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <CategoryForm
          show={showForm}
          onHide={() => {
            setShowForm(false);
            setEditingCategory(null);
          }}
          onSubmit={handleFormSubmit}
          category={editingCategory}
        />
      )}
    </div>
  );
};

export default Categories;
