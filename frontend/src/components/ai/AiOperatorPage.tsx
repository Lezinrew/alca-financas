import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Lock, Send } from 'lucide-react';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { ErrorNotice, LedgerStateBadge, SpaceKindBadge, StateLegend } from './AiBits';
import { OperationCard } from './OperationCard';
import { ProposalCard } from './ProposalCard';
import { ReasonDialog } from './ReasonDialog';
import { RunHistory } from './RunHistory';
import { RunProgress } from './RunProgress';
import { RunResult } from './RunResult';
import { TracePanel } from './TracePanel';
import { aiApi } from './aiApi';
import { type AiApiError, toAiApiError } from './aiErrors';
import {
  DASH, effectCounts, effectTotals, formatDecimalMoney, hasRunResult, payableStatusLabel, proposalKindLabel, spaceKindLabel,
} from './aiFormat';
import type { AiOperation, AiProposal, AiStatus, CreateRunPayload, RequestableTask } from './aiTypes';
import { newIdempotencyKey } from './idempotency';
import { useAiRequest } from './useAiRequest';
import { useRunPolling } from './useRunPolling';
import './ai-operator.css';

const MAX_MESSAGE = 2000;
const HISTORY_SIZE = 5;
/** Quantos pedidos ainda sem resposta guardam a chave de idempotência (limite de memória). */
const MAX_PENDING_INTENTS = 20;
const UNFINISHED = new Set(['queued', 'running', 'waiting_review', 'needs_reconciliation']);

const TASK_OPTIONS: Array<{ id: RequestableTask; title: string; hint: string; examples: string[] }> = [
  {
    id: 'finance_question', title: 'Pergunta sobre finanças', hint: 'Consulta os dados do aplicativo. Não grava nada.',
    examples: ['Quanto falta pagar das contas de outubro?', 'Quais contas vencem nesta semana?'],
  },
  {
    id: 'statement_import', title: 'Buscar extrato no e-mail', hint: 'Procura o extrato, lê o anexo e prepara uma prévia para você revisar.',
    examples: ['Buscar o extrato de setembro no e-mail e preparar a importação.'],
  },
];

const isRequestable = (value: string): value is RequestableTask => TASK_OPTIONS.some(option => option.id === value);

type Availability =
  | { kind: 'loading' }
  | { kind: 'ready'; status: AiStatus }
  | { kind: 'disabled' }
  | { kind: 'nosession' }
  | { kind: 'forbidden' }
  | { kind: 'error'; error: AiApiError };

/**
 * Decide o que a tela pode oferecer a partir de `GET /status`.
 *
 * IA desligada, sessão do backend novo ausente (401) e falta de autorização
 * (403) NÃO são erros do aplicativo: o titular continua logado e o resto do
 * sistema funciona. Por isso viram estados explicados, sem deslogar.
 */
const resolveAvailability = (data: AiStatus | null, error: AiApiError | null): Availability => {
  if (error) {
    if (error.status === 401) return { kind: 'nosession' };
    if (error.code === 'ai_disabled') return { kind: 'disabled' };
    if (error.status === 403) return { kind: 'forbidden' };
    return { kind: 'error', error };
  }
  if (!data) return { kind: 'loading' };
  return data.enabled ? { kind: 'ready', status: data } : { kind: 'disabled' };
};

const UNAVAILABLE_TEXT: Record<'disabled' | 'nosession' | 'forbidden', { title: string; body: string }> = {
  disabled: {
    title: 'O operador está desativado',
    body: 'O operador de IA está desligado no servidor e não aceita pedidos agora. Nenhum dado foi alterado.',
  },
  nosession: {
    title: 'Falta iniciar a sessão do operador',
    body: 'O operador usa uma sessão própria do novo servidor, que ainda não foi iniciada neste navegador. Você continua conectado ao Alça Finanças.',
  },
  forbidden: {
    title: 'Seu usuário não tem autorização para o operador',
    body: 'O acesso ao operador depende de uma autorização concedida pelo titular do espaço financeiro. Sem ela, a tela não envia pedidos.',
  },
};

function Unavailable({ kind, onRetry, checking }: { kind: 'disabled' | 'nosession' | 'forbidden'; onRetry: () => void; checking: boolean }) {
  const text = UNAVAILABLE_TEXT[kind];
  return <section className="ai-panel" aria-labelledby="ai-unavailable-title">
    <h2 id="ai-unavailable-title">{text.title}</h2>
    <p>{text.body}</p>
    <p>O restante do aplicativo continua funcionando normalmente: <Link className="ai-link" to="/financial-expenses">Contas a pagar</Link>, <Link className="ai-link" to="/import">Importar</Link> e os demais menus não dependem do operador.</p>
    <div className="ai-actions">
      <button type="button" className="ai-button" onClick={onRetry} disabled={checking}>{checking ? 'Verificando…' : 'Verificar novamente'}</button>
    </div>
  </section>;
}

const money = (value: unknown) => formatDecimalMoney(value) ?? DASH;

/** Linhas do diálogo de aprovação: exatamente o que muda, em texto corrido (lido bem por leitor de tela). */
const approvalDetails = (proposal: AiProposal): Array<[string, ReactNode]> => {
  const rows: Array<[string, ReactNode]> = [];
  const space = proposal.scope?.financial_space;
  const accounts = proposal.scope?.accounts ?? [];
  const effect = proposal.effect;
  if (space) rows.push(['Espaço', `${space.name} (${spaceKindLabel(space.kind)})`]);
  if (accounts.length) rows.push(['Conta', accounts.map(account => account.name).join(', ')]);
  if (effect?.before || effect?.after) {
    rows.push(['Pago', `de ${money(effect.before?.paid)} para ${money(effect.after?.paid)}`]);
    rows.push(['Restante', `de ${money(effect.before?.remaining)} para ${money(effect.after?.remaining)}`]);
    rows.push(['Situação', `de ${payableStatusLabel(effect.before?.status)} para ${payableStatusLabel(effect.after?.status)}`]);
  }
  // Mesmas contagens e totais da prévia (itens, duplicados, entradas, saídas...):
  // o diálogo repete exatamente o que o titular leu no cartão.
  rows.push(...effectCounts(effect), ...effectTotals(effect));
  rows.push(['Versão da proposta', String(proposal.version)]);
  return rows;
};

const APPROVAL_EFFECT: Record<string, string> = {
  payable_payment: 'Ao aprovar, o aplicativo registra este pagamento na conta a pagar.',
  statement_import: 'Ao aprovar, os itens novos do extrato entram no aplicativo como transações. Os duplicados não são importados.',
  reverse_operation: 'Ao aprovar, o aplicativo grava uma compensação que desfaz a operação original. O histórico é preservado.',
};

/**
 * Tela do operador de IA (contrato, seção 12).
 *
 * Fluxo: pedido -> andamento real -> resultado com fontes -> proposta para
 * revisão -> aprovação -> resultado aplicado, com cancelar, corrigir, desfazer
 * e rastrear. Nada é gravado sem aprovação explícita nesta tela.
 *
 * `pollSchedule` existe para os testes usarem intervalos curtos; a rota usa o
 * padrão do `useRunPolling`.
 */
export default function AiOperatorPage({ pollSchedule }: { pollSchedule?: readonly number[] }) {
  const [searchParams] = useSearchParams();
  const traceId = useId();
  const status = useAiRequest('status', signal => aiApi.getStatus({ signal }));
  const availability = resolveAvailability(status.data, status.error);
  const ready = availability.kind === 'ready' ? availability.status : null;

  const [spaceId, setSpaceId] = useState<string | null>(null);
  const spaces = ready?.spaces ?? [];
  const space = spaces.find(item => item.id === spaceId) ?? spaces[0] ?? null;
  // Espaço selecionado AGORA, lido depois de um `await`: a resposta de um envio
  // pode chegar quando o titular já trocou de espaço (ver `submit`).
  const currentSpaceId = useRef<string | null>(null);
  currentSpaceId.current = space?.id ?? null;
  const emailDisabled = ready?.flags.email === false;
  const writeDisabled = ready?.flags.write === false;

  const [taskChoice, setTask] = useState<RequestableTask>('finance_question');
  // A tarefa efetiva nunca é uma opção desligada no servidor. Sem isto, "Refazer
  // pedido" de uma importação antiga deixaria o rádio desabilitado E marcado, e o
  // envio sairia como busca no e-mail mesmo com o e-mail desligado.
  const task: RequestableTask = emailDisabled && taskChoice === 'statement_import' ? 'finance_question' : taskChoice;
  const [message, setMessage] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<AiApiError | null>(null);
  const submitLock = useRef(false);
  // Uma intenção = um conteúdo de pedido (tarefa + texto + espaço). Cada conteúdo
  // ainda SEM resposta 202 guarda a própria chave: se o envio falhar, o titular
  // editar o texto e depois voltar ao original, o reenvio usa a chave original.
  // A primeira tentativa pode ter chegado ao servidor (resposta perdida na rede),
  // e uma chave nova criaria uma segunda execução do mesmo pedido.
  const intents = useRef(new Map<string, string>());
  // Pedidos enviados nesta sessão, para mostrar o texto e refazer após "Corrigir".
  const sent = useRef(new Map<string, CreateRunPayload>());

  const [activeRunId, setActiveRunId] = useState<string | null>(() => searchParams.get('run'));
  const polling = useRunPolling(ready ? activeRunId : null, { schedule: pollSchedule });
  const run = polling.run;

  // Proposta de compensação criada por "Desfazer" nesta visita; pertence à execução aberta.
  const [extra, setExtra] = useState<{ runId: string; proposalId: string } | null>(null);
  const proposalIds = Array.from(new Set([
    ...(run?.proposal_ids ?? []),
    ...(extra && extra.runId === activeRunId ? [extra.proposalId] : []),
  ]));
  const proposals = useAiRequest(
    ready && proposalIds.length ? `proposals:${proposalIds.join(',')}` : null,
    signal => Promise.all(proposalIds.map(proposalId => aiApi.getProposal(proposalId, { signal }))),
  );
  const proposalList = proposals.data ?? [];
  const operationIds = Array.from(new Set([
    ...(run?.operation_ids ?? []),
    ...proposalList.map(proposal => proposal.operation_id).filter((value): value is string => !!value),
  ]));
  const operations = useAiRequest(
    ready && operationIds.length ? `operations:${operationIds.join(',')}` : null,
    signal => Promise.all(operationIds.map(operationId => aiApi.getOperation(operationId, { signal }))),
  );
  const operationList = operations.data ?? [];

  const history = useAiRequest(
    ready && space ? `runs:${space.id}` : null,
    signal => aiApi.listRuns({ financial_space_id: space?.id, limit: HISTORY_SIZE }, { signal }),
  );

  const [notice, setNotice] = useState('');
  const [traceOpen, setTraceOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<AiApiError | null>(null);
  const cancelLock = useRef(false);
  const [approving, setApproving] = useState<AiProposal | null>(null);
  const [approveError, setApproveError] = useState<AiApiError | null>(null);
  const [correcting, setCorrecting] = useState<AiProposal | null>(null);
  const [undoing, setUndoing] = useState<AiOperation | null>(null);

  const messageField = useRef<HTMLTextAreaElement>(null);
  const runHeading = useRef<HTMLHeadingElement>(null);
  const proposalHeading = useRef<HTMLHeadingElement>(null);
  const traceHeading = useRef<HTMLHeadingElement>(null);
  // Foco gerenciado: depois de uma ação, o teclado e o leitor de tela vão para
  // onde o resultado aparece. O contador dispara o efeito mesmo com alvo repetido.
  const [focusRequest, setFocusRequest] = useState<{ target: 'run' | 'message' | 'proposal' | 'trace'; token: number } | null>(null);
  const focusOn = useCallback((target: 'run' | 'message' | 'proposal' | 'trace') => {
    setFocusRequest(previous => ({ target, token: (previous?.token ?? 0) + 1 }));
  }, []);
  useEffect(() => {
    if (!focusRequest) return;
    const targets = { run: runHeading, message: messageField, proposal: proposalHeading, trace: traceHeading };
    targets[focusRequest.target].current?.focus();
  }, [focusRequest]);

  const reloadStatus = status.reload;
  const reloadHistory = history.reload;
  const refreshRun = polling.refresh;

  /** Sessão perdida ou IA desligada no meio do uso: reavalia a disponibilidade da tela. */
  const noteFailure = useCallback((error: AiApiError) => {
    if (error.status === 401 || error.code === 'ai_disabled') reloadStatus();
    return error;
  }, [reloadStatus]);
  const pollError = polling.error;
  useEffect(() => { if (pollError) noteFailure(pollError); }, [pollError, noteFailure]);

  const reloadProposals = proposals.reload;
  const reloadOperations = operations.reload;

  // O histórico acompanha a execução aberta: cada mudança de estado atualiza a lista.
  // E quando a MESMA execução muda de estado (aprovada -> aplicando -> concluída),
  // a proposta e as operações mudaram junto no servidor. Os ids continuam os mesmos,
  // então nada seria buscado de novo: sem esta reconsulta a tela mostraria a operação
  // gravada ao lado de uma proposta ainda "Aprovada".
  const runKey = run?.run_id ?? null;
  const runStatus = run?.status;
  const lastSeen = useRef<{ runKey: string; status: string } | null>(null);
  useEffect(() => {
    if (!runKey || !runStatus) return;
    const previous = lastSeen.current;
    lastSeen.current = { runKey, status: runStatus };
    reloadHistory();
    if (previous && previous.runKey === runKey && previous.status !== runStatus) { reloadProposals(); reloadOperations(); }
  }, [runKey, runStatus, reloadHistory, reloadProposals, reloadOperations]);

  // Ao entrar na tela, retoma a execução que ainda espera algo (em andamento ou
  // aguardando revisão), para uma proposta pendente não ficar esquecida.
  const resumed = useRef(false);
  const historyRuns = history.data?.runs ?? null;
  useEffect(() => {
    if (resumed.current || !historyRuns) return;
    resumed.current = true;
    if (activeRunId) return;
    const pending = historyRuns.find(item => UNFINISHED.has(item.status));
    if (pending) setActiveRunId(pending.run_id);
  }, [historyRuns, activeRunId]);

  /** Reconsulta tudo o que a execução aberta mostra (andamento, propostas e o que foi gravado). */
  const refreshOpenRun = () => { refreshRun(); reloadProposals(); reloadOperations(); };

  const openRun = (runId: string) => {
    // Abrir a execução que já está aberta não muda `activeRunId`, então nada seria
    // refeito sozinho (o acompanhamento para em "aguardando revisão"). Nesse caso
    // "abrir" significa reconsultar, mantendo o que já está na tela.
    if (runId === activeRunId) refreshOpenRun();
    else { setActiveRunId(runId); setExtra(null); setTraceOpen(false); }
    setCancelError(null); setNotice('');
    focusOn('run');
  };

  const changeSpace = (nextId: string) => {
    // Execução, proposta e operação pertencem a UM espaço. Trocar de espaço fecha o
    // que está aberto: nada do espaço anterior pode ficar na tela (muito menos
    // aprovável) sob o cabeçalho do novo.
    setSpaceId(nextId); setActiveRunId(null); setExtra(null); setTraceOpen(false); setCancelError(null); setNotice('');
    setSubmitError(null); setFormError('');
    // O novo espaço pode ter a própria execução pendente: libera a retomada automática.
    resumed.current = false;
  };

  // `needs_reconciliation` também bloqueia: a tela pede "não repita o pedido"
  // enquanto o servidor confirma se a gravação anterior foi concluída.
  const runBusy = !!run && (run.status === 'queued' || run.status === 'running' || run.status === 'needs_reconciliation');
  const currentTask = TASK_OPTIONS.find(option => option.id === task) ?? TASK_OPTIONS[0];

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    // Trava por ref: um segundo clique antes do re-render não cria outro envio.
    // `runBusy` repete aqui a regra do botão desabilitado: o formulário também pode
    // ser enviado sem passar pelo botão.
    if (submitLock.current || !space || runBusy) return;
    const text = message.trim();
    if (!text) { setFormError('Escreva o pedido antes de enviar.'); messageField.current?.focus(); return; }
    // `financial_space_id` só ESCOLHE entre os espaços do usuário; o servidor valida
    // e resolve tenant, ator e contas. `local_only`: esta tela nunca pede nuvem.
    const payload: CreateRunPayload = { task, message: text, financial_space_id: space.id, privacy: 'local_only', input_refs: [] };
    const fingerprint = JSON.stringify(payload);
    let idempotencyKey = intents.current.get(fingerprint);
    if (!idempotencyKey) {
      idempotencyKey = newIdempotencyKey();
      // Map preserva a ordem de inserção: ao encher, sai a intenção mais antiga.
      const oldest = intents.current.keys().next();
      if (intents.current.size >= MAX_PENDING_INTENTS && !oldest.done) intents.current.delete(oldest.value);
      intents.current.set(fingerprint, idempotencyKey);
    }
    submitLock.current = true; setSubmitting(true); setSubmitError(null); setFormError(''); setNotice('');
    try {
      const accepted = await aiApi.createRun(payload, { idempotencyKey });
      // Só aqui a intenção termina. Se a resposta se perder, a chave continua
      // valendo e o reenvio recebe a MESMA execução do servidor.
      intents.current.delete(fingerprint);
      sent.current.set(accepted.run_id, payload);
      // Só limpa o campo se ele ainda mostra o que foi enviado (o titular pode ter
      // começado a escrever outro pedido enquanto este estava em voo).
      setMessage(current => (current.trim() === text ? '' : current));
      if (currentSpaceId.current === space.id) {
        openRun(accepted.run_id);
        reloadHistory();
      } else {
        // O titular trocou de espaço antes de a resposta chegar. Abrir aqui mostraria
        // uma execução do espaço anterior sob o cabeçalho e o histórico do novo.
        setNotice(`O pedido foi aceito no espaço "${space.name}". Volte a esse espaço para acompanhar a execução.`);
      }
    } catch (error) {
      setSubmitError(noteFailure(toAiApiError(error)));
    } finally {
      submitLock.current = false; setSubmitting(false);
    }
  };

  const cancel = async () => {
    if (!run || cancelLock.current) return;
    cancelLock.current = true; setCancelling(true); setCancelError(null);
    try {
      await aiApi.cancelRun(run.run_id);
      refreshRun(); reloadHistory();
    } catch (error) {
      setCancelError(noteFailure(toAiApiError(error)));
    } finally {
      cancelLock.current = false; setCancelling(false);
    }
  };

  const confirmApproval = async () => {
    if (!approving) return;
    setApproveError(null);
    try {
      // Hash e versão são os que o titular viu nesta prévia. Se algo mudou no
      // servidor, ele recusa em vez de aplicar um conteúdo diferente do aprovado.
      const accepted = await aiApi.approveProposal(approving.proposal_id, { payload_hash: approving.payload_hash, version: approving.version });
      setApproving(null);
      // A proposta mudou de estado no servidor: a prévia que está na tela (com o
      // botão "Aprovar") não vale mais, qualquer que seja a forma da resposta.
      // - `run_id` de OUTRA execução (a que aplica, forma da spec): a tela passa a
      //   acompanhá-la, e a proposta é buscada de novo junto com ela.
      // - mesmo `run_id`, ou nenhum: nada mudaria sozinho (o acompanhamento está
      //   parado em "aguardando revisão"), então execução, proposta e operações são
      //   reconsultadas. Sem isso a tela ficaria com "Aprovar" ativo depois de aprovar.
      if (accepted.run_id && accepted.run_id !== activeRunId) openRun(accepted.run_id);
      else { refreshOpenRun(); focusOn('run'); }
      setNotice('Proposta aprovada. A gravação aparece em "Andamento" assim que o servidor confirmar; se demorar, use "Atualizar".');
      reloadHistory();
    } catch (error) {
      const failure = noteFailure(toAiApiError(error));
      // Não relançamos: o ConfirmDialog mostraria um texto fixo, e aqui queremos
      // a mensagem segura do servidor com o código de rastreio.
      setApproveError(failure);
      if (failure.status === 409) reloadProposals();
    }
  };

  /** Recoloca o pedido original no formulário, com a correção quando houver. */
  const refill = (reason?: string) => {
    const original = run ? sent.current.get(run.run_id) : undefined;
    // Se a tarefa original estiver desligada no servidor (busca no e-mail), a
    // tarefa efetiva cai para "pergunta" (ver `task`) e o rádio explica o motivo.
    if (original) setTask(original.task);
    else if (run && isRequestable(run.task)) setTask(run.task);
    const parts = [original?.message, reason ? `Correção: ${reason}` : ''].filter(Boolean);
    if (parts.length) setMessage(parts.join('\n\n'));
    focusOn('message');
  };

  const submitCorrection = async (reason: string) => {
    if (!correcting) return;
    try {
      await aiApi.rejectProposal(correcting.proposal_id, reason);
    } catch (error) {
      throw noteFailure(toAiApiError(error));
    }
    setCorrecting(null);
    setNotice('Proposta rejeitada; nada foi gravado. O pedido voltou para o formulário com a sua correção: revise e envie de novo.');
    refill(reason);
    reloadProposals(); refreshRun(); reloadHistory();
  };

  const submitUndo = async (reason: string) => {
    if (!undoing || !activeRunId) return;
    let created;
    try {
      created = await aiApi.reverseOperation(undoing.operation_id, reason);
    } catch (error) {
      throw noteFailure(toAiApiError(error));
    }
    setUndoing(null);
    setExtra({ runId: activeRunId, proposalId: created.proposal_id });
    setNotice('Proposta de compensação criada. Nada foi desfeito ainda: revise e aprove a proposta abaixo.');
    focusOn('proposal');
  };

  const showTrace = () => { setTraceOpen(true); focusOn('trace'); };

  return <div className="ai-operator ai-page">
    <div className="ai-header">
      <p className="ai-headline">Peça, confira e aprove</p>
      <p className="ai-muted">O operador busca e prepara. Nada é gravado sem a sua aprovação.</p>
    </div>

    {availability.kind === 'loading' && <p className="ai-panel" role="status">Verificando o operador…</p>}
    {availability.kind === 'error' && <ErrorNotice error={availability.error} title="Não foi possível verificar o operador." onRetry={reloadStatus} />}
    {(availability.kind === 'disabled' || availability.kind === 'nosession' || availability.kind === 'forbidden')
      && <Unavailable kind={availability.kind} onRetry={reloadStatus} checking={status.loading} />}

    {ready && <>
      <section className="ai-panel ai-context" aria-label="Espaço financeiro e privacidade">
        {spaces.length === 0
          ? <p>Nenhum espaço financeiro está vinculado ao seu usuário. Sem um espaço, o operador não tem o que consultar.</p>
          : spaces.length === 1
            ? <p className="ai-space-line"><span className="ai-muted">Espaço financeiro em uso:</span> <strong>{space?.name}</strong> <SpaceKindBadge kind={space?.kind} /></p>
            : <div className="ai-space-line">
              <label htmlFor="ai-space" className="ai-label">Espaço financeiro em uso</label>
              <select id="ai-space" className="ai-select" value={space?.id ?? ''} onChange={event => changeSpace(event.target.value)}>
                {spaces.map(item => <option key={item.id} value={item.id}>{item.name} — {spaceKindLabel(item.kind)}</option>)}
              </select>
              <SpaceKindBadge kind={space?.kind} />
            </div>}
        <p className="ai-privacy"><Lock size={16} aria-hidden="true" /><span><strong>Processamento local.</strong> Os pedidos desta tela são interpretados no servidor do Alça Finanças e não são enviados a serviços externos de IA.</span></p>
      </section>

      {space && <div className="ai-layout">
        <div className="ai-main">
          <section className="ai-panel" aria-labelledby="ai-request-title">
            <h2 id="ai-request-title">Novo pedido</h2>
            <form onSubmit={event => void submit(event)} noValidate>
              <fieldset className="ai-tasks">
                <legend>Tipo de tarefa</legend>
                <div className="ai-task-grid">
                  {TASK_OPTIONS.map(option => {
                    const disabled = option.id === 'statement_import' && emailDisabled;
                    return <label key={option.id} className="ai-task-option">
                      <input type="radio" name="ai-task" value={option.id} checked={task === option.id} disabled={disabled} onChange={() => setTask(option.id)} />
                      <span><strong>{option.title}</strong><span className="ai-muted ai-small">{disabled ? 'A busca no e-mail está desativada no servidor.' : option.hint}</span></span>
                    </label>;
                  })}
                </div>
              </fieldset>

              <label htmlFor="ai-message" className="ai-label">Seu pedido</label>
              <textarea id="ai-message" ref={messageField} className="ai-textarea" rows={3} maxLength={MAX_MESSAGE} value={message}
                aria-describedby="ai-message-hint" aria-invalid={!!formError}
                onChange={event => { setMessage(event.target.value); if (formError) setFormError(''); }} />
              <p id="ai-message-hint" className={formError ? 'ai-field-error' : 'ai-muted ai-small'} role={formError ? 'alert' : undefined}>
                {formError || 'Escreva em português, como falaria com uma pessoa. Use um exemplo abaixo para começar.'}
              </p>

              <p id="ai-examples-label" className="ai-muted ai-small">Exemplos:</p>
              <ul className="ai-examples" aria-labelledby="ai-examples-label">
                {currentTask.examples.map(example => <li key={example}>
                  <button type="button" className="ai-chip" onClick={() => { setMessage(example); setFormError(''); messageField.current?.focus(); }}>{example}</button>
                </li>)}
              </ul>

              {submitError && <ErrorNotice error={submitError} title="O pedido não foi enviado." />}
              {submitError?.retryable && <p className="ai-muted ai-small">Enviar de novo repete o mesmo pedido; o servidor não cria uma execução duplicada.</p>}

              <div className="ai-actions">
                <button type="submit" className="ai-button ai-button-primary" disabled={submitting || runBusy}>
                  <Send size={16} aria-hidden="true" />{submitting ? 'Enviando…' : 'Enviar pedido'}
                </button>
              </div>
              {runBusy && <p className="ai-muted ai-small">{run?.status === 'needs_reconciliation'
                ? 'O servidor ainda confere a última gravação. Aguarde a confirmação antes de enviar outro pedido.'
                : 'Há uma execução em andamento. Aguarde terminar ou cancele para enviar outro pedido.'}</p>}
            </form>
          </section>

          {notice && <p className="ai-notice" role="status">{notice}</p>}

          {activeRunId && <section className="ai-panel" aria-labelledby="ai-run-title" aria-busy={polling.loading}>
            <h2 id="ai-run-title" ref={runHeading} tabIndex={-1}>Andamento</h2>
            {run
              ? <RunProgress run={run} requestText={sent.current.get(run.run_id)?.message} polling={polling.polling} pollError={polling.error}
                onRetry={refreshRun} onRefresh={refreshOpenRun} onCancel={() => void cancel()} cancelling={cancelling} cancelError={cancelError}
                traceOpen={traceOpen} traceId={traceId} onToggleTrace={() => setTraceOpen(open => !open)} />
              : polling.error
                ? <ErrorNotice error={polling.error} title="Não foi possível abrir esta execução." onRetry={polling.error.retryable ? refreshRun : undefined} />
                : <p role="status">Abrindo a execução…</p>}
          </section>}

          {run && hasRunResult(run) && <section className="ai-panel" aria-labelledby="ai-result-title">
            <h2 id="ai-result-title">Resultado</h2>
            <RunResult run={run} />
          </section>}

          {proposalIds.length > 0 && <section className="ai-panel" aria-labelledby="ai-proposal-title" aria-busy={proposals.loading}>
            <h2 id="ai-proposal-title" ref={proposalHeading} tabIndex={-1}>{proposalIds.length === 1 ? 'Proposta para revisão' : 'Propostas para revisão'}</h2>
            {proposals.error && <ErrorNotice error={proposals.error} title="Não foi possível carregar a proposta." onRetry={proposals.reload} />}
            {!proposals.error && proposals.data === null && <p role="status">Carregando a proposta…</p>}
            <div className="ai-stack">
              {proposalList.map(proposal => <ProposalCard key={proposal.proposal_id} proposal={proposal} writeDisabled={writeDisabled}
                onApprove={item => { setApproveError(null); setApproving(item); }} onCorrect={setCorrecting}
                onRedo={() => { setNotice('O pedido voltou para o formulário. Revise e envie de novo para gerar uma prévia atual.'); refill(); }}
                onTrace={showTrace} />)}
            </div>
          </section>}

          {operationIds.length > 0 && <section className="ai-panel" aria-labelledby="ai-applied-title" aria-busy={operations.loading}>
            <h2 id="ai-applied-title">Resultado aplicado</h2>
            {operations.error && <ErrorNotice error={operations.error} title="Não foi possível carregar o que foi gravado." onRetry={operations.reload} />}
            {!operations.error && operations.data === null && <p role="status">Carregando o que foi gravado…</p>}
            <div className="ai-stack">
              {operationList.map(operation => <OperationCard key={operation.operation_id} operation={operation} writeDisabled={writeDisabled} onUndo={setUndoing} />)}
            </div>
          </section>}

          {(proposalIds.length > 0 || operationIds.length > 0) && <div className="ai-panel"><StateLegend /></div>}

          {traceOpen && run && <TracePanel id={traceId} ref={traceHeading} run={run} proposals={proposalList} operations={operationList} />}
        </div>

        <aside className="ai-side" aria-label="Histórico">
          <RunHistory runs={historyRuns} loading={history.loading} error={history.error} activeRunId={activeRunId} onOpen={openRun} onRetry={reloadHistory} />
        </aside>
      </div>}
    </>}

    {approving && <ConfirmDialog
      title="Aprovar proposta"
      subject={proposalKindLabel(approving.kind)}
      details={approvalDetails(approving)}
      confirmLabel="Aprovar e aplicar"
      onConfirm={confirmApproval}
      onClose={() => setApproving(null)}
      consequence={<>
        <p>{APPROVAL_EFFECT[approving.kind] ?? 'Ao aprovar, o aplicativo grava a alteração descrita acima.'} Nenhum dinheiro é movimentado no banco.</p>
        {approving.effect?.state_after && <p>Estado depois de aplicar: <LedgerStateBadge state={approving.effect.state_after} /></p>}
        {(approving.ambiguities?.length ?? 0) > 0 && <p><strong>Atenção:</strong> esta proposta tem {approving.ambiguities?.length === 1 ? '1 ponto ambíguo' : `${approving.ambiguities?.length} pontos ambíguos`}. Aprove só se já conferiu.</p>}
        <p className="app-dialog-muted">A aprovação vale apenas para esta versão. Se os dados mudarem antes de aplicar, o servidor recusa e pede uma nova prévia.</p>
        {approveError && <div className="ai-operator"><ErrorNotice error={approveError} title="A aprovação não foi registrada." /></div>}
      </>}
    />}

    {correcting && <ReasonDialog
      title="Corrigir proposta"
      description="A proposta atual é rejeitada, nada é gravado, e o pedido volta para o formulário com a sua correção."
      reasonLabel="O que precisa ser corrigido?"
      confirmLabel="Rejeitar e refazer o pedido"
      onSubmit={submitCorrection}
      onClose={() => setCorrecting(null)}
    />}

    {undoing && <ReasonDialog
      title="Desfazer operação"
      description="Será criada uma proposta de compensação. Ela só desfaz a operação depois que você revisar e aprovar."
      reasonLabel="Por que desfazer?"
      confirmLabel="Criar proposta de compensação"
      danger
      onSubmit={submitUndo}
      onClose={() => setUndoing(null)}
    />}
  </div>;
}
