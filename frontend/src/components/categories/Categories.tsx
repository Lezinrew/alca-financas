import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { categoriesAPI } from '../../utils/api';
import CategoryForm from './CategoryForm';

const Categories = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);

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
      setCategories(response.data);
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

  const handleEditCategory = (category: any) => {
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

  const handleFormSubmit = async (formData) => {
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
        <button
          onClick={handleAddCategory}
          className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
        >
          <i className="bi bi-plus-circle"></i>
          Nova Categoria
        </button>
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
