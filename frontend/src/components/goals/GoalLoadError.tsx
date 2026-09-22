import React from 'react';

interface GoalLoadErrorProps {
  title: string;
  message: string;
  onRetry: () => void;
  onBack?: () => void;
}

/** Bloco de erro de carregamento das Metas, sempre com "Tentar novamente". */
export const GoalLoadError: React.FC<GoalLoadErrorProps> = ({ title, message, onRetry, onBack }) => (
  <div role="alert" className="card-base p-8 text-center border border-red-200 dark:border-red-800">
    <i className="bi bi-exclamation-triangle-fill text-3xl text-red-600 dark:text-red-400 block mb-3" aria-hidden="true" />
    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h2>
    <p className="mt-2 text-slate-600 dark:text-slate-300">{message}</p>
    <div className="mt-4 flex flex-wrap justify-center gap-3">
      <button
        type="button"
        onClick={onRetry}
        className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:hover:bg-slate-600"
      >
        <i className="bi bi-arrow-clockwise" aria-hidden="true" />
        Tentar novamente
      </button>
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium text-indigo-600 hover:underline dark:text-indigo-400"
        >
          Voltar às metas
        </button>
      )}
    </div>
  </div>
);

export default GoalLoadError;
