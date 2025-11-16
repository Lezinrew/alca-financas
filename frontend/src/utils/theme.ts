/**
 * Design Tokens e Utilitários de Tema
 * 
 * Este arquivo centraliza todas as classes e constantes relacionadas ao tema
 * para garantir consistência visual em todo o projeto.
 */

// Cores do tema dark (Mobills-like)
export const darkTheme = {
  surface: {
    base: '#0f172a', // Background principal da página
    card: '#1a1d29', // Background de cards
    elevated: '#252836', // Cards elevados, headers de tabela
    hover: '#2d3142', // Estados de hover
  },
  border: {
    default: 'rgba(148, 163, 184, 0.2)', // 20% opacity
    subtle: 'rgba(148, 163, 184, 0.1)', // 10% opacity
    strong: 'rgba(148, 163, 184, 0.3)', // 30% opacity
  },
  text: {
    primary: '#ffffff', // Texto principal
    secondary: '#e2e8f0', // Texto secundário
    tertiary: '#cbd5e1', // Texto terciário
    muted: '#94a3b8', // Texto muted
  },
} as const;

// Classes Tailwind padronizadas para uso em componentes
export const themeClasses = {
  // Backgrounds
  bg: {
    page: 'bg-slate-50 dark:bg-[#0f172a]',
    card: 'bg-white dark:bg-[#1a1d29]',
    cardElevated: 'bg-white dark:bg-[#252836]',
    sidebar: 'bg-[#1a1d29]',
    header: 'bg-white dark:bg-[#1a1d29]',
  },
  // Borders
  border: {
    default: 'border-slate-200 dark:border-slate-700/50',
    subtle: 'border-slate-200 dark:border-slate-700/30',
    strong: 'border-slate-300 dark:border-slate-600/50',
  },
  // Text
  text: {
    primary: 'text-slate-900 dark:text-white',
    secondary: 'text-slate-700 dark:text-slate-300',
    tertiary: 'text-slate-600 dark:text-slate-400',
    muted: 'text-slate-500 dark:text-slate-500',
  },
  // Hover states
  hover: {
    card: 'hover:bg-slate-50 dark:hover:bg-[#252836]',
    button: 'hover:bg-slate-100 dark:hover:bg-slate-700',
  },
} as const;

/**
 * Helper para gerar classes de tema consistentes
 */
export const cn = (...classes: (string | undefined | null | false)[]): string => {
  return classes.filter(Boolean).join(' ');
};

