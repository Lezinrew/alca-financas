import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Plus, RotateCcw } from 'lucide-react';
import { financialExpensesAPI, formatCurrency, type ExpenseOverview, type FinancialExpense } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import ExpenseList from './ExpenseList';
import { ExpenseDialog } from './ExpenseDialog';
import { ExpenseFormDialog } from './ExpenseFormDialog';
import { useFinancialExpenses, useGeneralOverview } from './useFinancialExpenses';
import './financial-expenses.css';

const categories = ['moradia', 'educação', 'saúde', 'transporte', 'veículos', 'cartões', 'dívidas', 'família', 'serviços', 'utilidades', 'impostos', 'alimentação', 'pessoal', 'outros'];
const initialFilters = { status: '', category: '', responsible: '', recurring: '' };
const statusLabels: Record<string, string> = { pending: 'Pendentes', partial: 'Parciais', paid: 'Pagas', overdue: 'Vencidas', canceled: 'Canceladas' };
const money = (value: number | string) => Number(value) || 0;

function FinancialSummary({ data, loading, error, retry }: {
  data: ExpenseOverview | null; loading: boolean; error: string; retry: () => void;
}) {
  return <section aria-label="Resumo das contas filtradas" aria-busy={loading}>
    {error && <div className="payables-error" role="alert">Resumo indisponível. {error} <button className="payables-button" onClick={retry}>Tentar novamente</button></div>}
    <div className="payables-summary">
      {([
        ['Previsto', data?.expected, 'Valor das contas, exceto canceladas'],
        ['Pago nessas contas', data?.paid, 'Inclui pagamentos parciais registrados'],
        ['Em aberto', data?.remaining, 'Saldo das pendentes e parciais'],
      ] as const).map(([label, value, detail], i) => <article key={label} className={`payables-summary-card ${i === 2 ? 'payables-balance-card' : ''}`}>
        <h2>{label}</h2><p className="payables-metric">{value == null ? '—' : formatCurrency(value)}</p><p className="payables-muted text-sm">{detail}</p>
      </article>)}
    </div>
    <p className="payables-muted mt-3 text-sm">Valores registrados nas contas selecionadas; não representam conciliação bancária nem pagamentos feitos necessariamente neste mês.</p>
    <div role="status" aria-live="polite" className="payables-counts mt-4">
      {loading ? 'Atualizando resumo…' : data ? <>
        <strong>{data.total} contas</strong><span>{data.counts.paid} pagas</span><span>{data.counts.pending} pendentes</span><span>{data.counts.partial} parciais</span><span>{data.counts.canceled} canceladas</span>
        <span className="payables-overdue-count">{data.counts.overdue} vencidas entre as pendentes e parciais</span>
      </> : 'Resumo indisponível'}
    </div>
  </section>;
}

function DueGroups({ data, label }: {data: ExpenseOverview; label: string}) {
  const names = { before: 'Vencimentos anteriores ao mês', month: 'Vencimentos neste mês', after: 'Próximos meses', undated: 'Sem vencimento' };
  return <section className="payables-panel" aria-label="Distribuição por vencimento">
    <h2 className="text-lg font-semibold">Em aberto por vencimento</h2>
    <p className="payables-muted text-sm mt-1 mb-4">Referência: {label}. Apenas contas abertas nos filtros atuais. Vencimento e competência podem ser diferentes. Atrasos são calculados na data da consulta.</p>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Object.entries(names).map(([key, title]) => {
      const group = data.due_groups[key as keyof typeof names];
      return <div key={key}><p className="payables-muted text-sm">{title}</p><p className="text-lg font-semibold tabular-nums">{formatCurrency(group.remaining)}</p><p className="payables-muted text-sm">{group.count} contas</p></div>;
    })}</div>
  </section>;
}

export default function FinancialExpensesPage() {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [today] = useState(() => new Date());
  const [period, setPeriod] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`);
  const [view, setView] = useState<'month' | 'all'>('month');
  const [draftFilters, setDraftFilters] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [showContext, setShowContext] = useState(false);
  const [editing, setEditing] = useState<FinancialExpense | null | undefined>(undefined);
  const [action, setAction] = useState<{kind: 'pay' | 'delete'; row: FinancialExpense} | null>(null);
  const [busy, setBusy] = useState(false);
  const actionLock = useRef(false);
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const [importText, setImportText] = useState('');
  const [importBusy, setImportBusy] = useState(false);
  const importLock = useRef(false);
  const [importResult, setImportResult] = useState('');
  const [year, month] = period.split('-').map(Number);
  const label = new Date(year, month - 1, 1).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  const query = useMemo(() => ({
    ...(view === 'month' ? { month, year } : {}),
    status: filters.status || undefined, category: filters.category || undefined,
    responsible: filters.responsible.trim() || undefined,
    is_recurring: filters.recurring === '' ? undefined : filters.recurring === 'yes',
    reference_month: month, reference_year: year,
  }), [view, month, year, filters]);
  const enabled = isAuthenticated && !authLoading;
  const { list, overview } = useFinancialExpenses(query, page, revision, enabled);
  const context = useGeneralOverview(query, revision, enabled && showContext && view === 'month');
  const refresh = () => setRevision(value => value + 1);
  const changePeriod = (value: string) => {
    if (/^\d{4}-\d{2}$/.test(value) && Number(value.slice(0, 4)) >= 2000 && Number(value.slice(0, 4)) <= 2100) { setPeriod(value); setPage(1); }
  };
  const stepMonth = (step: number) => {
    const next = new Date(year, month - 1 + step, 1);
    changePeriod(`${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`);
  };
  const openAction = (kind: 'pay' | 'delete', row: FinancialExpense) => { setActionError(''); setAction({ kind, row }); };
  const confirmAction = async () => {
    if (!action || actionLock.current) return;
    actionLock.current = true; setBusy(true); setActionError('');
    try {
      if (action.kind === 'pay') await financialExpensesAPI.markPaid(action.row.id);
      else await financialExpensesAPI.delete(action.row.id);
      setNotice(action.kind === 'pay' ? 'Pagamento registrado na conta.' : 'Conta excluída.');
      setAction(null); setPage(1); refresh();
    } catch {
      setActionError('Não foi possível confirmar a operação. Confira os dados atualizados antes de tentar novamente.');
    } finally { actionLock.current = false; setBusy(false); }
  };
  const importAccounts = async () => {
    if (importLock.current) return;
    const ids = [...new Set((importText.match(/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/gi) || []).map(id => id.toLowerCase()))];
    if (!ids.length) { setImportResult('Informe pelo menos um identificador válido de transação.'); return; }
    importLock.current = true; setImportBusy(true); setImportResult('');
    try {
      const { data } = await financialExpensesAPI.createFromTransactions(ids);
      setImportResult(`${data.created.length} criadas · ${data.skipped.length} já existentes ou ignoradas · ${data.errors.length} com erro.`);
      if (data.created.length) { setImportText(''); setPage(1); refresh(); }
    } catch { setImportResult('Importação indisponível. Tente novamente.'); }
    finally { importLock.current = false; setImportBusy(false); }
  };
  const hasFilters = Object.values(filters).some(Boolean);
  const filtersChanged = JSON.stringify(filters) !== JSON.stringify(draftFilters);

  return <div className="payables space-y-6">
    <div className="payables-header">
      <div><p className="text-xl font-semibold">Seu mês, com clareza</p><p className="payables-muted mt-1">Acompanhe suas contas e registre o que já foi pago.</p></div>
      <button className="payables-button payables-button-primary" onClick={() => setEditing(null)}><Plus size={18} aria-hidden="true" />Nova conta</button>
    </div>
    <section className="payables-panel" aria-label="Visão e filtros">
      <div className="payables-toolbar justify-between">
        <div className="payables-view-switch" role="group" aria-label="Visão das contas">
          <button className="payables-button" aria-pressed={view === 'month'} onClick={() => { setView('month'); setPage(1); }}>Mensal</button>
          <button className="payables-button" aria-pressed={view === 'all'} onClick={() => { setView('all'); setPage(1); }}>Visão geral</button>
        </div>
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <button className="payables-button" aria-label="Mês anterior" onClick={() => stepMonth(-1)}><ChevronLeft size={18} /></button>
          <label className="sr-only" htmlFor="expense-period">{view === 'month' ? 'Competência' : 'Mês de referência dos vencimentos'}</label>
          <input id="expense-period" type="month" min="2000-01" max="2100-12" value={period} onChange={event => changePeriod(event.target.value)} className="native-input-themed max-w-full" />
          <button className="payables-button" aria-label="Próximo mês" onClick={() => stepMonth(1)}><ChevronRight size={18} /></button>
          <button className="payables-button" onClick={() => changePeriod(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`)}>Este mês</button>
        </div>
      </div>
      <p className="mt-4 font-medium">{view === 'month' ? `Competência: ${label}` : 'Todas as competências, incluindo contas sem competência'}</p>
      <p className="payables-muted text-sm mt-1">{view === 'month' ? 'Resumo e lista seguem o mês de competência e os filtros aplicados.' : `O mês de referência (${label}) organiza apenas os grupos de vencimento abaixo.`}</p>
      <form className="payables-filters mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5" onSubmit={event => { event.preventDefault(); setFilters({ ...draftFilters }); setPage(1); }}>
        <label>Categoria<select className="native-select-themed w-full" value={draftFilters.category} onChange={e => setDraftFilters({ ...draftFilters, category: e.target.value })}><option value="">Todas</option>{categories.map(category => <option key={category}>{category}</option>)}</select></label>
        <label>Responsável<input className="native-input-themed w-full" placeholder="Buscar por nome" value={draftFilters.responsible} onChange={e => setDraftFilters({ ...draftFilters, responsible: e.target.value })} /></label>
        <label>Situação<select className="native-select-themed w-full" value={draftFilters.status} onChange={e => setDraftFilters({ ...draftFilters, status: e.target.value })}><option value="">Todas</option>{Object.entries(statusLabels).map(([value, title]) => <option key={value} value={value}>{title}{value === 'pending' || value === 'partial' ? ' (inclui vencidas)' : ''}</option>)}</select></label>
        <label>Recorrência<select className="native-select-themed w-full" value={draftFilters.recurring} onChange={e => setDraftFilters({ ...draftFilters, recurring: e.target.value })}><option value="">Todas</option><option value="yes">Recorrentes</option><option value="no">Avulsas</option></select></label>
        <div className="flex items-end gap-2"><button type="submit" className="payables-button payables-button-primary">Aplicar</button><button type="button" className="payables-button" aria-label="Limpar filtros" onClick={() => { setFilters(initialFilters); setDraftFilters(initialFilters); setPage(1); }}><RotateCcw size={16} /></button></div>
      </form>
      {filtersChanged && <p className="payables-notice mt-3" role="status">Há filtros ainda não aplicados. Clique em Aplicar para atualizar.</p>}
      {hasFilters && <p className="payables-muted mt-3 text-sm">Filtros aplicados: {[filters.category, filters.responsible && `Responsável: ${filters.responsible}`, statusLabels[filters.status], filters.recurring && (filters.recurring === 'yes' ? 'Recorrentes' : 'Avulsas')].filter(Boolean).join(' · ')}</p>}
    </section>
    {authLoading && <p role="status">Verificando acesso…</p>}
    <FinancialSummary {...overview} retry={refresh} />
    {notice && <p className="payables-notice" role="status">{notice}</p>}
    <section aria-label="Lista de contas">
      <div className="flex flex-wrap justify-between items-center gap-2 mb-4"><h2 className="text-lg font-semibold">{view === 'month' ? `Contas de ${label}` : 'Todas as contas'}</h2><button className="payables-button" onClick={refresh} disabled={list.loading}>Atualizar</button></div>
      {list.error ? <div role="alert" className="payables-error">Lista indisponível. {list.error} <button className="payables-button" onClick={refresh}>Tentar novamente</button></div> : list.loading ? <div className="payables-panel" role="status" aria-busy="true">Carregando contas…</div> : list.data?.data.length ? <ExpenseList rows={list.data.data} loading={false} onEdit={setEditing} onPay={row => openAction('pay', row)} onDelete={row => openAction('delete', row)} /> : <div className="payables-panel"><h3 className="font-semibold">{hasFilters ? 'Nenhuma conta corresponde aos filtros' : view === 'month' ? 'Nenhuma conta nesta competência' : 'Nenhuma conta cadastrada'}</h3><p className="payables-muted mt-2">{hasFilters ? 'Experimente limpar os filtros ou escolher outro período.' : 'Escolha outro período ou cadastre uma nova conta.'}</p></div>}
      {list.data && list.data.pagination.total > 0 && <nav aria-label="Paginação das contas" className="flex flex-wrap items-center justify-between gap-3 mt-4">
        <p className="payables-muted text-sm">{list.data.pagination.total} contas · página {page} de {Math.max(1, list.data.pagination.pages)}. Totais consideram todas as páginas.</p>
        <div className="flex gap-2"><button className="payables-button" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Anterior</button><button className="payables-button" disabled={page >= list.data.pagination.pages} onClick={() => setPage(p => p + 1)}>Próxima</button></div>
      </nav>}
    </section>
    {view === 'all' && overview.data && <DueGroups data={overview.data} label={label} />}
    {view === 'month' && <section className="payables-panel">
      <button className="payables-button" aria-expanded={showContext} aria-controls="expense-other-periods" onClick={() => setShowContext(!showContext)}>Outros períodos {showContext ? '−' : '+'}</button>
      <p className="payables-muted text-sm mt-2">Fora da competência selecionada. Não incluídos nos totais acima. Os demais filtros continuam valendo.</p>
      {showContext && <div id="expense-other-periods" className="mt-4">
        {context.loading ? <p role="status">Carregando outros períodos…</p> : context.error ? <p role="alert">Contexto indisponível. <button className="payables-button" onClick={refresh}>Tentar novamente</button></p> : context.data && <div className="grid sm:grid-cols-3 gap-4">
          {([['before', 'Competências anteriores'], ['after', 'Competências futuras'], ['undated', 'Sem competência']] as const).map(([key, title]) => <div key={key}><h3 className="payables-muted text-sm">{title}</h3><p className="font-semibold text-lg tabular-nums">{formatCurrency(context.data!.competency_groups[key].remaining)}</p><p className="payables-muted text-sm">{context.data!.competency_groups[key].count} contas em aberto</p></div>)}
        </div>}
        <button className="payables-button mt-4" onClick={() => { setView('all'); setPage(1); }}>Ver visão geral e vencimentos</button>
      </div>}
    </section>}
    <details className="payables-panel"><summary className="cursor-pointer font-medium">Mais opções: importação e planejamento</summary><div className="mt-4 space-y-3">
      <p className="payables-muted">Crie contas a partir de transações existentes. Essa operação adiciona contas à lista.</p>
      <label className="block" htmlFor="expense-import">Identificadores das transações</label><textarea id="expense-import" className="native-input-themed w-full" rows={3} value={importText} onChange={e => setImportText(e.target.value)} />
      <button className="payables-button" disabled={importBusy} onClick={() => void importAccounts()}>{importBusy ? 'Importando…' : 'Importar contas das transações'}</button>
      {importResult && <p role="status">{importResult}</p>}
      <p><Link className="payables-button" to="/planning">Abrir planejamento</Link></p>
    </div></details>
    {editing !== undefined && <ExpenseFormDialog expense={editing} defaultMonth={month} defaultYear={year} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); setNotice('Conta salva.'); setPage(1); refresh(); }} />}
    {action && <ExpenseDialog title={action.kind === 'pay' ? 'Registrar pagamento integral' : 'Excluir conta'} busy={busy} onClose={() => { if (!busy) setAction(null); }}>
      <div className="p-4"><p className="font-semibold text-lg break-words">{action.row.title}</p>
      {action.kind === 'pay' ? <>
        <dl className="grid grid-cols-2 gap-3 my-5"><dt>Previsto</dt><dd>{formatCurrency(money(action.row.amount_expected))}</dd><dt>Já pago</dt><dd>{formatCurrency(money(action.row.amount_paid))}</dd><dt>Saldo a quitar</dt><dd className="font-bold">{formatCurrency(Math.max(0, money(action.row.amount_expected) - money(action.row.amount_paid)))}</dd></dl>
        <p>O total pago desta conta será igual ao previsto. A data do registro será a data atual. Nenhuma transferência bancária será feita.</p>
        <p className="payables-muted text-sm mt-2">Para registrar um pagamento parcial ou outra data, cancele e use Editar.</p>
      </> : <p className="my-4">Esta conta será removida da lista e dos totais. Não há opção de desfazer nesta tela. A transação de origem, quando houver, permanece no livro.</p>}
      {actionError && <p className="payables-error mt-4" role="alert">{actionError}</p>}
      <div className="flex flex-wrap justify-end gap-3 mt-6"><button className="payables-button" disabled={busy} onClick={() => setAction(null)}>Cancelar</button><button className={`payables-button ${action.kind === 'pay' ? 'payables-button-primary' : 'payables-button-danger'}`} disabled={busy} onClick={() => void confirmAction()}>{busy ? 'Confirmando…' : action.kind === 'pay' ? 'Confirmar registro' : 'Confirmar exclusão'}</button></div>
      </div>
    </ExpenseDialog>}
  </div>;
}
