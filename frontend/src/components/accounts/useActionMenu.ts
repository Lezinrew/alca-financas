import { useEffect, useRef, useState } from 'react';

/**
 * Estado de um menu de ações por item: fecha com Escape (devolvendo o foco ao
 * botão que o abriu) e ao clicar fora do contêiner.
 */
export function useActionMenu<T extends HTMLElement = HTMLDivElement>() {
  const [open, setOpen] = useState(false);
  const container = useRef<T>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        setOpen(false);
        trigger.current?.focus();
      }
    };
    const onPointerDown = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onPointerDown);
    };
  }, [open]);

  return { open, setOpen, toggle: () => setOpen(value => !value), close: () => setOpen(false), container, trigger };
}

export const MENU_TRIGGER_CLASS = 'flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white';
export const MENU_ITEM_CLASS = 'dropdown-item flex w-full items-center gap-2 px-4 py-3 text-left text-sm';
