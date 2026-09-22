import React from 'react';
import { MENU_ITEM_CLASS, MENU_TRIGGER_CLASS, useActionMenu } from '../accounts/useActionMenu';
import type { Category } from './types';

interface CategoryCardProps {
  category: Category;
  onEdit: (category: Category) => void;
  onDelete: (category: Category) => void;
}

const CategoryCard: React.FC<CategoryCardProps> = ({ category, onEdit, onDelete }) => {
  const menu = useActionMenu();
  const run = (action: () => void) => { menu.close(); action(); };

  return (
    <div className="card-elevated relative flex items-center justify-between gap-2 p-4 hover:border-slate-300 hover:shadow-sm dark:hover:border-slate-600">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: category.color }} aria-hidden="true">
          <i className={`bi bi-${category.icon} text-white`}></i>
        </div>
        <div className="min-w-0">
          <p className="truncate font-medium text-slate-900 dark:text-white">{category.name}</p>
          {category.description && <p className="text-xs text-slate-500 dark:text-slate-400">{category.description}</p>}
        </div>
      </div>

      <div ref={menu.container} className="relative flex-shrink-0">
        <button ref={menu.trigger} type="button" onClick={menu.toggle} aria-haspopup="menu" aria-expanded={menu.open}
          aria-label={`Mais ações para ${category.name}`} className={MENU_TRIGGER_CLASS}>
          <i className="bi bi-three-dots-vertical" aria-hidden="true"></i>
        </button>

        {menu.open && (
          <div role="menu" aria-label={`Ações de ${category.name}`} className="dropdown-menu absolute right-0 top-full z-50 mt-1 w-40 py-1">
            <button type="button" role="menuitem" onClick={() => run(() => onEdit(category))} className={MENU_ITEM_CLASS}>
              <i className="bi bi-pencil text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
              <span>Editar</span>
            </button>
            <button type="button" role="menuitem" onClick={() => run(() => onDelete(category))} className={`${MENU_ITEM_CLASS} text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20`}>
              <i className="bi bi-trash" aria-hidden="true"></i>
              <span>Excluir</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CategoryCard;
