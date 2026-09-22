interface AdminUnavailableProps {
  /** O que ficou indisponível, em minúsculas (ex.: "as estatísticas"). */
  what: string;
  onRetry: () => void;
}

/** Bloco de falha de carregamento: nunca deixa a página parecer vazia ou com zeros falsos. */
export function AdminUnavailable({ what, onRetry }: AdminUnavailableProps) {
  return (
    <div role="alert" className="admin-card-shell p-6 text-center">
      <p className="font-medium text-slate-900 dark:text-white">Indisponível.</p>
      <p className="mt-1 text-sm text-slate-600 dark:text-dark-text-secondary">
        Não foi possível carregar {what}.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="admin-outline-btn mt-4 min-h-[44px] rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-50 dark:text-dark-text-secondary"
      >
        Tentar novamente
      </button>
    </div>
  );
}
