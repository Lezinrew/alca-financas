import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardList } from 'lucide-react';
import { formatCurrency } from '../../utils/api';
import type { PayablesSummary } from '../../utils/payablesSummary';

interface PayablesSummaryBlockProps {
  summary: PayablesSummary | null;
  /** id do título no modal (unicidade por página) */
  titleId?: string;
}

export function PayablesSummaryBlock({ summary, titleId = 'payables-summary-title' }: PayablesSummaryBlockProps) {
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);

  if (!summary) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        className="card-base w-full p-4 text-left transition-all hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-300">
              <ClipboardList className="h-5 w-5" aria-hidden />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-600 dark:text-slate-400">Contas a pagar</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-500">Competência: {summary.monthLabel}</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                <span className="text-amber-600 dark:text-amber-400">{summary.openCount} em aberto</span>
                <span className="mx-2 text-slate-300 dark:text-slate-600">·</span>
                <span className="text-emerald-600 dark:text-emerald-400">{summary.paidCount} pagas</span>
              </p>
            </div>
          </div>
          <span className="text-sm font-medium text-violet-600 dark:text-violet-400 shrink-0">
            Ver detalhes <i className="bi bi-chevron-right ml-1" aria-hidden />
          </span>
        </div>
      </button>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          onClick={() => setModalOpen(false)}
        >
          <div className="modal-content w-full max-w-lg p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <h2 id={titleId} className="text-lg font-semibold text-slate-900 dark:text-white">
                Contas a pagar
              </h2>
              <button
                type="button"
                className="rounded-lg p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
                onClick={() => setModalOpen(false)}
                aria-label="Fechar"
              >
                <i className="bi bi-x-lg text-lg" />
              </button>
            </div>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">Competência: {summary.monthLabel}</p>

            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-amber-200/80 bg-amber-50/90 p-4 dark:border-amber-900/40 dark:bg-amber-950/30">
                <p className="text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-200/90">
                  A pagar (abertas)
                </p>
                <p className="mt-2 text-3xl font-bold text-amber-900 dark:text-amber-100">{summary.openCount}</p>
                <p className="mt-1 text-sm text-amber-900/80 dark:text-amber-100/80">
                  {formatCurrency(summary.openRemainingSum)} em falta
                  {summary.sumsPartial && ' (amostra)'}
                </p>
              </div>
              <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/90 p-4 dark:border-emerald-900/40 dark:bg-emerald-950/30">
                <p className="text-xs font-medium uppercase tracking-wide text-emerald-800 dark:text-emerald-200/90">
                  Pagas
                </p>
                <p className="mt-2 text-3xl font-bold text-emerald-900 dark:text-emerald-100">{summary.paidCount}</p>
                <p className="mt-1 text-sm text-emerald-900/80 dark:text-emerald-100/80">
                  {formatCurrency(summary.paidSumExpected)} previsto
                  {summary.sumsPartial && ' (amostra)'}
                </p>
              </div>
            </div>

            <ul className="mt-4 space-y-2 text-sm text-slate-600 dark:text-slate-400">
              <li>
                <span className="font-medium text-slate-800 dark:text-slate-200">Vencidas (em aberto):</span>{' '}
                {summary.overdueCount}
              </li>
              {summary.canceledCount > 0 && (
                <li>
                  <span className="font-medium text-slate-800 dark:text-slate-200">Canceladas no mês:</span>{' '}
                  {summary.canceledCount}
                </li>
              )}
              <li>
                <span className="font-medium text-slate-800 dark:text-slate-200">Total no mês:</span>{' '}
                {summary.totalInMonth} despesa(s) com esta competência
              </li>
            </ul>

            {summary.sumsPartial && (
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-500">
                Os valores em reais somam até {summary.sampleSize} despesas carregadas; o total de itens no mês é{' '}
                {summary.totalInMonth}.
              </p>
            )}

            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                onClick={() => setModalOpen(false)}
              >
                Fechar
              </button>
              <button
                type="button"
                className="rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 dark:bg-violet-500 dark:hover:bg-violet-600"
                onClick={() => {
                  setModalOpen(false);
                  navigate('/financial-expenses');
                }}
              >
                Ir para Contas a pagar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
