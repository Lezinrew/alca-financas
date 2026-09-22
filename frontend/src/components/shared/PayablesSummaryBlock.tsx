import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardList } from 'lucide-react';
import { formatCurrency } from '../../utils/api';
import type { PayablesSummary } from '../../utils/payablesSummary';
import { AppDialog } from './AppDialog';

interface PayablesSummaryBlockProps {
  /** null = resumo indisponível (falha de consulta). Nunca significa "sem contas". */
  summary: PayablesSummary | null;
  loading?: boolean;
  onRetry?: () => void;
  /** Mantido por compatibilidade; o diálogo gera o próprio id. */
  titleId?: string;
}

export function PayablesSummaryBlock({ summary, loading = false, onRetry }: PayablesSummaryBlockProps) {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);

  if (loading) {
    return <div className="card-base w-full p-4" role="status" aria-busy="true">
      <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Contas a pagar</p>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Carregando resumo…</p>
    </div>;
  }

  if (!summary) {
    return <div className="card-base w-full p-4" role="alert">
      <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Contas a pagar</p>
      <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">Resumo indisponível no momento. Os valores não foram carregados.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {onRetry && <button type="button" onClick={onRetry} className="min-h-[44px] rounded-lg border border-slate-300 px-3 text-sm font-medium dark:border-slate-600">Tentar novamente</button>}
        <button type="button" onClick={() => navigate('/financial-expenses')} className="min-h-[44px] rounded-lg px-3 text-sm font-medium text-violet-700 dark:text-violet-300">Abrir Contas a pagar</button>
      </div>
    </div>;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        aria-haspopup="dialog"
        className="card-base w-full min-h-[44px] p-4 text-left transition-all hover:shadow-md focus:outline-none focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">
              <ClipboardList className="h-5 w-5" aria-hidden />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Contas a pagar</p>
              <p className="text-xs text-slate-600 dark:text-slate-400">Competência: {summary.monthLabel}</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                <span className="text-amber-700 dark:text-amber-300">{summary.openCount} em aberto</span>
                {summary.overdueCount > 0 && <span className="ml-1 text-sm font-medium text-red-700 dark:text-red-300">({summary.overdueCount} vencidas)</span>}
                <span className="mx-2 text-slate-400 dark:text-slate-500" aria-hidden>·</span>
                <span className="text-emerald-700 dark:text-emerald-300">{summary.paidCount} pagas</span>
              </p>
              <p className="text-sm text-slate-700 dark:text-slate-300">{formatCurrency(summary.openRemainingSum)} a pagar</p>
            </div>
          </div>
          <span className="text-sm font-medium text-violet-700 dark:text-violet-300 shrink-0">
            Ver detalhes <i className="bi bi-chevron-right ml-1" aria-hidden />
          </span>
        </div>
      </button>

      {modalOpen && (
        <AppDialog title="Contas a pagar" description={`Competência: ${summary.monthLabel}. Mesmos números da aba Contas a pagar.`} onClose={() => setModalOpen(false)} size="sm">
          <div className="app-dialog-body">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/40">
                <p className="text-xs font-medium uppercase tracking-wide text-amber-900 dark:text-amber-200">Em aberto</p>
                <p className="mt-2 text-3xl font-bold text-amber-900 dark:text-amber-100">{summary.openCount}</p>
                <p className="mt-1 text-sm text-amber-900 dark:text-amber-100">{formatCurrency(summary.openRemainingSum)} a pagar</p>
                <p className="mt-1 text-sm text-amber-900 dark:text-amber-100">{summary.overdueCount} vencidas · {summary.partialCount} parciais</p>
              </div>
              <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950/40">
                <p className="text-xs font-medium uppercase tracking-wide text-emerald-900 dark:text-emerald-200">Pagas</p>
                <p className="mt-2 text-3xl font-bold text-emerald-900 dark:text-emerald-100">{summary.paidCount}</p>
                <p className="mt-1 text-sm text-emerald-900 dark:text-emerald-100">{formatCurrency(summary.paidSum)} pagos nessas contas</p>
              </div>
            </div>
            <dl className="app-dialog-details mt-4">
              <dt>Previsto no mês</dt><dd>{formatCurrency(summary.expectedSum)}</dd>
              <dt>Total de contas</dt><dd>{summary.totalInMonth}{summary.canceledCount > 0 ? ` (${summary.canceledCount} canceladas)` : ''}</dd>
            </dl>
            <p className="app-dialog-muted">Valores registrados nas contas desta competência. Não representam conciliação bancária.</p>
            <div className="app-dialog-actions">
              <button type="button" className="app-dialog-button" onClick={() => setModalOpen(false)}>Fechar</button>
              <button type="button" className="app-dialog-button app-dialog-button-primary" onClick={() => { setModalOpen(false); navigate('/financial-expenses'); }}>Ir para Contas a pagar</button>
            </div>
          </div>
        </AppDialog>
      )}
    </>
  );
}
