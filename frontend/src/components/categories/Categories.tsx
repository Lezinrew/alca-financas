import { useState } from 'react';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';
import { categoriesAPI } from '../../utils/api';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import CategoryForm from './CategoryForm';
import CategoryCard from './CategoryCard';
import { downloadCategoryExampleFile } from './categoryExampleFile';
import { CATEGORY_DELETE_ERROR, categoryTypeNames, type Category, type CategoryPayload, type CategoryType } from './types';

const sections: Array<{ type: CategoryType; title: string; icon: string; header: string; heading: string; count: string; empty: string }> = [
  { type: 'income', title: 'Receitas', icon: 'bi-arrow-up-circle text-emerald-600', header: 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-100 dark:border-emerald-800/50', heading: 'text-emerald-900 dark:text-emerald-300', count: 'text-emerald-700 dark:text-emerald-400', empty: 'Nenhuma categoria de receita cadastrada' },
  { type: 'expense', title: 'Despesas', icon: 'bi-arrow-down-circle text-red-600', header: 'bg-red-50 dark:bg-red-900/20 border-red-100 dark:border-red-800/50', heading: 'text-red-900 dark:text-red-300', count: 'text-red-700 dark:text-red-400', empty: 'Nenhuma categoria de despesa cadastrada' },
];

async function fetchCategories(signal: AbortSignal): Promise<{ data: Category[] }> {
  const response = await categoriesAPI.getAll({ signal });
  const raw: unknown = response.data;
  const list = Array.isArray(raw) ? raw : (raw as { data?: unknown })?.data;
  return { data: Array.isArray(list) ? (list as Category[]) : [] };
}

const Categories = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [revision, setRevision] = useState(0);
  const [form, setForm] = useState<{ open: boolean; category: Category | null }>({ open: false, category: null });
  const [deleting, setDeleting] = useState<Category | null>(null);

  const enabled = isAuthenticated && !authLoading;
  const { data: categories, loading, error } = useKeyedRequest<Category[]>(String(revision), enabled, fetchCategories);
  const refresh = () => setRevision(value => value + 1);
  const closeForm = () => setForm({ open: false, category: null });

  const handleFormSubmit = async (formData: CategoryPayload) => {
    if (form.category) {
      await categoriesAPI.update(form.category.id, formData);
      toast.success('Categoria atualizada com sucesso!');
    } else {
      await categoriesAPI.create(formData);
      toast.success('Categoria criada com sucesso!');
    }
    closeForm();
    refresh();
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    await categoriesAPI.delete(deleting.id);
    toast.success('Categoria excluída com sucesso!');
    setDeleting(null);
    refresh();
  };

  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="text-center" role="status">
          <div className="mx-auto mb-3 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600"></div>
          <p className="text-slate-600 dark:text-slate-300">Carregando categorias...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Categorias</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Organize suas receitas e despesas</p>
        </div>
        <button type="button" onClick={() => setForm({ open: true, category: null })}
          className="flex min-h-[44px] items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          <i className="bi bi-plus-circle" aria-hidden="true"></i>
          Nova categoria
        </button>
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
          <span className="text-red-800 dark:text-red-200">Indisponível. {error}</span>
          <button type="button" onClick={refresh} className="min-h-[44px] rounded-lg border border-red-300 px-4 text-sm font-medium text-red-800 hover:bg-red-100 dark:border-red-700 dark:text-red-200 dark:hover:bg-red-900/40">Tentar novamente</button>
        </div>
      )}

      {sections.map(section => {
        const items = (categories ?? []).filter(category => category.type === section.type);
        return (
          <section key={section.type} className="card-base" aria-labelledby={`categories-${section.type}`}>
            <div className={`border-b px-6 py-4 ${section.header}`}>
              <div className="flex items-center gap-2">
                <i className={`bi ${section.icon}`} aria-hidden="true"></i>
                <h2 id={`categories-${section.type}`} className={`text-lg font-semibold ${section.heading}`}>{section.title}</h2>
                <span className={`ml-auto text-sm ${section.count}`}>{categories ? `${items.length} categorias` : '—'}</span>
              </div>
            </div>
            <div className="p-6">
              {categories && items.length === 0 && <p className="py-8 text-center text-slate-500 dark:text-slate-400">{section.empty}</p>}
              {items.length > 0 && (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {items.map(category => (
                    <CategoryCard key={category.id} category={category} onEdit={cat => setForm({ open: true, category: cat })} onDelete={setDeleting} />
                  ))}
                </div>
              )}
            </div>
          </section>
        );
      })}

      <details className="text-sm text-slate-600 dark:text-slate-300">
        <summary className="min-h-[44px] cursor-pointer py-2 font-medium">Importar categorias em lote</summary>
        <p className="mt-2">Baixe um arquivo de exemplo com categorias, ícones e cores disponíveis e importe-o nas Configurações.</p>
        <button type="button" onClick={() => { downloadCategoryExampleFile(); toast.success('Arquivo de exemplo baixado.'); }}
          className="mt-2 flex min-h-[44px] items-center gap-2 rounded-lg border border-slate-300 px-4 font-medium text-slate-800 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-700">
          <i className="bi bi-file-earmark-arrow-down" aria-hidden="true"></i>
          Baixar exemplo
        </button>
      </details>

      {form.open && <CategoryForm onHide={closeForm} onSubmit={handleFormSubmit} category={form.category} />}

      {deleting && (
        <ConfirmDialog
          title="Excluir categoria"
          subject={deleting.name}
          details={[['Tipo', categoryTypeNames[deleting.type]]]}
          consequence={<p>A exclusão é permanente e não pode ser desfeita nesta tela. Categorias com transações vinculadas não podem ser excluídas: nesse caso a exclusão é recusada e nada é alterado.</p>}
          confirmLabel="Confirmar exclusão"
          danger
          onConfirm={confirmDelete}
          onClose={() => setDeleting(null)}
          errorMessage={CATEGORY_DELETE_ERROR}
        />
      )}
    </div>
  );
};

export default Categories;
