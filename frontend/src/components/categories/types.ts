export type CategoryType = 'income' | 'expense';

export interface Category {
  id: string;
  name: string;
  type: CategoryType;
  color: string;
  icon: string;
  description?: string;
}

export type CategoryPayload = Omit<Category, 'id'>;

export const categoryTypeNames: Record<CategoryType, string> = { income: 'Receita', expense: 'Despesa' };

export const CATEGORY_SAVE_ERROR = 'Não foi possível salvar a categoria. Suas alterações foram mantidas. Tente novamente.';
export const CATEGORY_DELETE_ERROR = 'Não foi possível excluir a categoria. Categorias com transações vinculadas não podem ser excluídas.';
