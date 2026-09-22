import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';
import { formatCurrency, accountsAPI } from '../../utils/api';
import { Account, AccountPayload } from '../../types/account';
import { useKeyedRequest } from '../../hooks/useKeyedRequest';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import AccountForm from './AccountForm';
import AccountCard from './AccountCard';
import { ACCOUNT_DELETE_ERROR, getAccountTypeName } from './accountLabels';

function SummaryCard({ title, help, value, tone, children }: { title: string; help: string; value: number | null; tone: 'blue' | 'purple'; children?: React.ReactNode }) {
  const badge = tone === 'blue' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400';
  return (
    <div className="card-base p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-600 dark:text-slate-400">{title}</p>
        <div className={`flex h-8 w-8 items-center justify-center rounded-full ${badge}`} aria-hidden="true"><i className="bi bi-currency-dollar text-sm"></i></div>
      </div>
      <p className="mb-1 text-xl font-bold tabular-nums text-slate-900 dark:text-white">{value === null ? '—' : formatCurrency(value)}</p>
      <p className="text-xs text-slate-500 dark:text-slate-400">{help}</p>
      {children}
    </div>
  );
}

const Accounts: React.FC = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [revision, setRevision] = useState(0);
  const [form, setForm] = useState<{ open: boolean; account: Account | null }>({ open: false, account: null });
  const [deleting, setDeleting] = useState<Account | null>(null);

  const enabled = isAuthenticated && !authLoading;
  const { data: accounts, loading, error } = useKeyedRequest<Account[]>(String(revision), enabled, signal => accountsAPI.getAll({ signal }));
  const refresh = () => setRevision(value => value + 1);
  const closeForm = () => setForm({ open: false, account: null });

  const handleFormSubmit = async (formData: AccountPayload) => {
    if (form.account?.id) {
      await accountsAPI.update(form.account.id, formData);
      toast.success('Conta atualizada com sucesso!');
    } else {
      await accountsAPI.create(formData);
      toast.success('Conta criada com sucesso!');
    }
    closeForm();
    refresh();
  };

  const confirmDelete = async () => {
    if (!deleting?.id) return;
    await accountsAPI.delete(deleting.id);
    toast.success('Conta excluída.');
    setDeleting(null);
    refresh();
  };

  if (authLoading || (loading && isAuthenticated)) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="text-center" role="status">
          <div className="mx-auto mb-3 h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600"></div>
          <p className="text-slate-600 dark:text-slate-300">Carregando contas...</p>
        </div>
      </div>
    );
  }

  // Apenas contas ativas; cartões de crédito ficam na página de cartões.
  const activeAccounts = (accounts ?? []).filter(
    acc => acc.is_active !== false && (acc as Account & { active?: boolean }).active !== false && acc.type !== 'credit_card',
  );
  const totalBalance = accounts ? activeAccounts.reduce((sum, acc) => sum + (acc.current_balance || 0), 0) : null;
  const projectedBalance = accounts ? activeAccounts.reduce((sum, acc) => sum + ((acc.projected_balance ?? acc.current_balance) || 0), 0) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Contas</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Gerencie suas contas bancárias e carteiras</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
          <span className="text-red-800 dark:text-red-200">Indisponível. {error}</span>
          <button type="button" onClick={refresh} className="min-h-[44px] rounded-lg border border-red-300 px-4 text-sm font-medium text-red-800 hover:bg-red-100 dark:border-red-700 dark:text-red-200 dark:hover:bg-red-900/40">Tentar novamente</button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="space-y-3 lg:col-span-3">
          <button type="button" onClick={() => setForm({ open: true, account: null })}
            className="card-base w-full border-2 border-dashed border-slate-300 p-8 text-center hover:border-purple-500 hover:bg-purple-50/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 dark:border-slate-700 dark:hover:border-purple-500 dark:hover:bg-purple-900/10">
            <span className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-purple-600 to-blue-600" aria-hidden="true">
              <i className="bi bi-plus-lg text-2xl text-white"></i>
            </span>
            <span className="mb-1 block text-base font-semibold text-slate-900 dark:text-white">Nova conta</span>
            <span className="block text-xs text-slate-500 dark:text-slate-300">Adicione uma nova conta bancária ou carteira</span>
          </button>

          {accounts && activeAccounts.length === 0 && (
            <div className="card-base p-8 text-center">
              <i className="bi bi-wallet2 mb-3 block text-5xl text-slate-300 dark:text-slate-600" aria-hidden="true"></i>
              <h2 className="mb-1 text-base font-semibold text-slate-700 dark:text-white">Nenhuma conta cadastrada</h2>
              <p className="text-sm text-slate-500 dark:text-slate-300">Comece adicionando sua primeira conta</p>
            </div>
          )}
          {activeAccounts.length > 0 && (
            <div className="space-y-3">
              {activeAccounts.map(account => (
                <AccountCard key={account.id} account={account} onEdit={acc => setForm({ open: true, account: acc })} onDelete={setDeleting} />
              ))}
            </div>
          )}
        </div>

        <section className="space-y-3" aria-label="Resumo das contas" aria-busy={loading}>
          <SummaryCard title="Saldo atual" help="Valor total em contas ativas (apenas transações pagas)" value={totalBalance} tone="blue" />
          <SummaryCard title="Saldo previsto" help="Projeção incluindo transações pendentes e futuras" value={projectedBalance} tone="purple">
            {totalBalance !== null && projectedBalance !== null && projectedBalance !== totalBalance && (
              <p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
                {projectedBalance > totalBalance ? '↑' : '↓'} {formatCurrency(Math.abs(projectedBalance - totalBalance))} de diferença
              </p>
            )}
          </SummaryCard>
        </section>
      </div>

      {form.open && <AccountForm onHide={closeForm} onSubmit={handleFormSubmit} account={form.account} />}

      {deleting && (
        <ConfirmDialog
          title="Excluir conta"
          subject={deleting.name}
          details={[['Tipo', getAccountTypeName(deleting.type)], ['Saldo atual', formatCurrency(deleting.current_balance ?? 0)]]}
          consequence={<p>A exclusão é permanente e não pode ser desfeita nesta tela. Contas com transações vinculadas não podem ser excluídas: nesse caso a exclusão é recusada e nada é alterado.</p>}
          confirmLabel="Confirmar exclusão"
          danger
          onConfirm={confirmDelete}
          onClose={() => setDeleting(null)}
          errorMessage={ACCOUNT_DELETE_ERROR}
        />
      )}
    </div>
  );
};

export default Accounts;
