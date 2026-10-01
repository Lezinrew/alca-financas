import { act, cleanup, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AiOperatorPage from './AiOperatorPage';
import { aiApi } from './aiApi';
import { AiApiError } from './aiErrors';
import {
  APPLIED_RUN, BUSINESS_SPACE, IMPORT_PROPOSAL, IMPORT_REVERSAL_PROPOSAL, PAYMENT_OPERATION, PAYMENT_PROPOSAL, PERSONAL_SPACE,
  QUESTION_DONE, REVERSAL_PROPOSAL, STATUS_READY, STATUS_SINGLE_SPACE, makeRun, step,
} from './fixtures';
import type { AiProposal, AiRun, ApprovalAccepted, RunAccepted } from './aiTypes';

// Dublê apenas da fronteira HTTP. Hooks, formatação, diálogos e a página são os reais.
vi.mock('./aiApi', () => ({
  aiApi: {
    getStatus: vi.fn(), createRun: vi.fn(), getRun: vi.fn(), listRuns: vi.fn(), cancelRun: vi.fn(),
    getProposal: vi.fn(), approveProposal: vi.fn(), rejectProposal: vi.fn(), getOperation: vi.fn(), reverseOperation: vi.fn(),
  },
}));

const api = vi.mocked(aiApi);

// Folga para máquina ocupada (a suíte roda ao lado de outras): os testes não dependem
// de tempo para passar, só não devem falhar por lentidão do ambiente.
vi.setConfig({ testTimeout: 30_000 });
configure({ asyncUtilTimeout: 10_000 });
const plain = (value: string | null | undefined) => (value ?? '').replace(/\u00a0/g, ' ');
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};
const apiError = (init: Partial<ConstructorParameters<typeof AiApiError>[0]> = {}) => new AiApiError({
  code: 'model_unavailable', retryable: true, safeMessage: 'Nenhum modelo autorizado está disponível agora.', traceId: 'rastreio-0503', status: 503, ...init,
});
const ACCEPTED: RunAccepted = { run_id: 'run-0001', status: 'queued', trace_id: 'rastreio-0001' };
const WAITING_PAYMENT = makeRun({ status: 'waiting_review', progress: { stage: 'waiting_review', steps: [step(1, 'Preparando a baixa', 'succeeded', 'finance.prepare_change')] }, proposal_ids: [PAYMENT_PROPOSAL.proposal_id] });
const WAITING_IMPORT = makeRun({ run_id: 'run-0002', task: 'statement_import', status: 'waiting_review', progress: { stage: 'waiting_review', steps: [] }, proposal_ids: [IMPORT_PROPOSAL.proposal_id] });
const UNAUTHORIZED = () => apiError({ code: 'unauthorized', retryable: false, status: 401, safeMessage: 'Sessão ausente ou expirada.' });

/** A página fica em /ai; as outras rotas existem para provar que ninguém foi redirecionado. */
const mount = (entry = '/ai') => render(
  <MemoryRouter initialEntries={[entry]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    <Routes>
      <Route path="/ai" element={<AiOperatorPage pollSchedule={[5]} />} />
      <Route path="/login" element={<p>TELA DE LOGIN</p>} />
      <Route path="*" element={<p>OUTRA TELA</p>} />
    </Routes>
  </MemoryRouter>,
);

const messageField = () => screen.findByLabelText('Seu pedido');
const sendButton = () => screen.getByRole('button', { name: 'Enviar pedido' });
const fillAndSend = async (text: string) => {
  fireEvent.change(await messageField(), { target: { value: text } });
  await userEvent.click(sendButton());
};
const runPanel = () => within(screen.getByRole('region', { name: 'Andamento' }));
const spaceSelect = () => screen.getByRole('combobox', { name: 'Espaço financeiro em uso' });
const proposalCard = async (name: string) => within(await screen.findByRole('article', { name: `Proposta: ${name}` }));
const rowCells = (scope: ReturnType<typeof within>, header: string) =>
  within(scope.getByRole('rowheader', { name: header }).closest('tr')!).getAllByRole('cell').map(cell => plain(cell.textContent));
/** Valor de um par rótulo/valor (dt/dd) dentro de um cartão. */
const pairIn = (scope: ReturnType<typeof within>, term: string) => plain(scope.getByText(term).closest('div')!.querySelector('dd')!.textContent);
const stageItem = (label: string) => within(runPanel().getByRole('list', { name: 'Etapas da execução' })).getByText(label).closest('li')!;

/** Entrega as respostas de GET /runs/{id} uma a uma, para observar cada etapa. */
const controlledRuns = () => {
  const waiters: Array<(run: AiRun) => void> = [];
  api.getRun.mockImplementation(() => new Promise<AiRun>(resolve => { waiters.push(resolve); }));
  return async (run: AiRun) => {
    await waitFor(() => expect(waiters.length).toBeGreaterThan(0));
    await act(async () => { waiters.shift()!(run); });
  };
};

beforeEach(() => {
  vi.resetAllMocks();
  api.getStatus.mockResolvedValue(STATUS_SINGLE_SPACE);
  api.listRuns.mockResolvedValue({ runs: [], next_cursor: null });
  api.createRun.mockResolvedValue(ACCEPTED);
  api.getRun.mockResolvedValue(QUESTION_DONE);
  api.getProposal.mockResolvedValue(PAYMENT_PROPOSAL);
  api.getOperation.mockResolvedValue(PAYMENT_OPERATION);
  api.cancelRun.mockResolvedValue(undefined);
  api.rejectProposal.mockResolvedValue(undefined);
});
afterEach(cleanup);

describe('pedido e andamento', () => {
  it('mostra o andamento real, etapa por etapa, conforme o servidor informa', async () => {
    const answer = controlledRuns();
    mount();
    await fillAndSend('Quanto falta pagar em outubro?');

    await answer(makeRun({ status: 'queued' }));
    expect(runPanel().getByRole('status')).toHaveTextContent('Na fila: a execução ainda não começou.');
    expect(runPanel().getByRole('status')).toHaveAttribute('aria-live', 'polite');
    expect(stageItem('Buscando')).toHaveTextContent('a seguir');
    expect(runPanel().getByText('Quanto falta pagar em outubro?')).toBeInTheDocument();

    await answer(makeRun({ status: 'running', progress: { stage: 'searching', steps: [step(1, 'Consultando contas a pagar', 'started')] } }));
    expect(stageItem('Buscando')).toHaveTextContent('em andamento');
    expect(stageItem('Buscando')).toHaveAttribute('aria-current', 'step');
    expect(stageItem('Lendo')).toHaveTextContent('a seguir');
    expect(runPanel().getByRole('status')).toHaveTextContent('Buscando: Consultando contas a pagar.');

    await answer(makeRun({ status: 'running', progress: { stage: 'reading', steps: [step(1, 'Consultando contas a pagar'), step(2, 'Lendo os lançamentos', 'started')] } }));
    expect(stageItem('Buscando')).toHaveTextContent('concluída');
    expect(stageItem('Buscando')).not.toHaveAttribute('aria-current');
    expect(stageItem('Lendo')).toHaveTextContent('em andamento');
    expect(stageItem('Preparando')).toHaveTextContent('a seguir');
    expect(runPanel().getByRole('status')).toHaveTextContent('Lendo: Lendo os lançamentos.');

    await answer(makeRun({ status: 'running', progress: { stage: 'preparing', steps: [step(1, 'Consultando contas a pagar'), step(2, 'Lendo os lançamentos'), step(3, 'Redigindo a resposta', 'started', 'model.generate')] } }));
    expect(stageItem('Lendo')).toHaveTextContent('concluída');
    expect(stageItem('Preparando')).toHaveTextContent('em andamento');
    expect(stageItem('Concluído')).toHaveTextContent('a seguir');

    await answer(QUESTION_DONE);
    expect(stageItem('Preparando')).toHaveTextContent('concluída');
    expect(stageItem('Concluído')).toHaveTextContent('concluída');
    expect(runPanel().getByRole('status')).toHaveTextContent('Execução concluída.');
    // Uma pergunta não passa por revisão nem grava nada: essas etapas não aparecem.
    expect(runPanel().queryByText('Aguardando revisão')).not.toBeInTheDocument();
    expect(runPanel().queryByText('Aplicado')).not.toBeInTheDocument();
  });

  it('envia a tarefa, o texto, o espaço em uso e sempre local_only; o foco vai para o andamento', async () => {
    mount();
    await fillAndSend('  Quais contas vencem nesta semana?  ');
    await screen.findByRole('region', { name: 'Andamento' });

    expect(api.createRun).toHaveBeenCalledExactlyOnceWith(
      { task: 'finance_question', message: 'Quais contas vencem nesta semana?', financial_space_id: PERSONAL_SPACE.id, privacy: 'local_only', input_refs: [] },
      { idempotencyKey: expect.stringMatching(/^[0-9a-f-]{36}$/) },
    );
    expect(api.getRun).toHaveBeenCalledWith('run-0001', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Andamento' })).toHaveFocus());
    expect(await messageField()).toHaveValue('');
  });

  it('bloqueia duplo envio enquanto o primeiro não respondeu', async () => {
    const pending = deferred<RunAccepted>();
    api.createRun.mockImplementation(() => pending.promise);
    mount();
    const field = await messageField();
    fireEvent.change(field, { target: { value: 'Quanto falta pagar em outubro?' } });
    const form = field.closest('form')!;
    fireEvent.submit(form); fireEvent.submit(form);
    fireEvent.click(screen.getByRole('button', { name: 'Enviando…' }));

    expect(api.createRun).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Enviando…' })).toBeDisabled();
    await act(async () => pending.resolve(ACCEPTED));
    expect(api.createRun).toHaveBeenCalledOnce();
  });

  it('não envia pedido vazio', async () => {
    mount();
    fireEvent.change(await messageField(), { target: { value: '   ' } });
    await userEvent.click(sendButton());
    expect(api.createRun).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent('Escreva o pedido antes de enviar.');
  });

  it('exemplo preenche o pedido e muda com o tipo de tarefa', async () => {
    mount();
    await userEvent.click(await screen.findByRole('button', { name: 'Quanto falta pagar das contas de outubro?' }));
    expect(await messageField()).toHaveValue('Quanto falta pagar das contas de outubro?');

    await userEvent.click(screen.getByRole('radio', { name: /Buscar extrato no e-mail/ }));
    await userEvent.click(screen.getByRole('button', { name: /Buscar o extrato de setembro no e-mail/ }));
    await userEvent.click(sendButton());
    expect(api.createRun).toHaveBeenCalledWith(expect.objectContaining({ task: 'statement_import', message: 'Buscar o extrato de setembro no e-mail e preparar a importação.' }), expect.anything());
  });

  it('cancelar chama a API uma única vez e mostra o estado devolvido pelo servidor', async () => {
    api.getRun.mockResolvedValue(makeRun({ status: 'running', progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo', 'started')] } }));
    const cancelling = deferred<void>();
    api.cancelRun.mockImplementation(() => cancelling.promise);
    mount('/ai?run=run-0001');
    const cancel = await screen.findByRole('button', { name: 'Cancelar' });

    // Dois cliques no mesmo instante, antes de a tela redesenhar o botão como desabilitado:
    // quem segura o segundo é a trava do próprio manipulador.
    act(() => { cancel.click(); cancel.click(); });
    expect(api.cancelRun).toHaveBeenCalledExactlyOnceWith('run-0001');
    expect(screen.getByRole('button', { name: 'Cancelando…' })).toBeDisabled();

    api.getRun.mockResolvedValue(makeRun({ status: 'cancelled', cancel_requested: true, progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo', 'failed')] } }));
    await act(async () => cancelling.resolve());
    await waitFor(() => expect(runPanel().getByRole('status')).toHaveTextContent('Execução cancelada.'));
    expect(stageItem('Lendo')).toHaveTextContent('cancelada');
    expect(screen.queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument();
  });

  it('execução terminada não oferece cancelar', async () => {
    mount('/ai?run=run-0001');
    await screen.findByText('Execução concluída.');
    expect(screen.queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument();
  });

  it('para de consultar quando a execução chega a um estado terminal', async () => {
    api.getRun.mockResolvedValueOnce(makeRun({ status: 'running', progress: { stage: 'searching', steps: [] } }));
    api.getRun.mockResolvedValueOnce(makeRun({ status: 'running', progress: { stage: 'reading', steps: [] } }));
    mount('/ai?run=run-0001');
    await screen.findByText('Execução concluída.');
    const calls = api.getRun.mock.calls.length;
    expect(calls).toBe(3);

    // Com intervalo de 5 ms, 120 ms dariam mais de vinte consultas se o polling continuasse.
    await act(async () => { await sleep(120); });
    expect(api.getRun).toHaveBeenCalledTimes(calls);
  });

  it('para de consultar em aguardando revisão e retoma só depois de uma ação', async () => {
    api.getRun.mockResolvedValue(WAITING_PAYMENT);
    mount('/ai?run=run-0001');
    await screen.findByText('Aguardando a sua revisão.');
    await act(async () => { await sleep(80); });
    expect(api.getRun).toHaveBeenCalledOnce();
    expect(stageItem('Aguardando revisão')).toHaveTextContent('aguardando você');
  });

  it('desmontar a tela aborta a consulta em voo', async () => {
    api.getRun.mockImplementation(() => new Promise<AiRun>(() => {}));
    const view = mount('/ai?run=run-0001');
    await waitFor(() => expect(api.getRun).toHaveBeenCalled());
    const signal = api.getRun.mock.calls[0][1]!.signal!;
    view.unmount();
    expect(signal.aborted).toBe(true);
  });
});

describe('resultado: fatos e fontes', () => {
  const factCard = async (label: string) => {
    const list = await screen.findByRole('list', { name: 'Fatos calculados' });
    return within(within(list).getByRole('heading', { name: label }).closest('li')!);
  };

  it('formata o valor decimal em string sem perda', async () => {
    api.getRun.mockResolvedValue({
      ...QUESTION_DONE,
      facts: [...(QUESTION_DONE.facts ?? []), { ...QUESTION_DONE.facts![0], key: 'payables.total', label: 'Total histórico', value: '123456789012345678.90' }],
    });
    mount('/ai?run=run-0001');
    expect(plain((await factCard('Falta pagar')).getByText(/1\.250,00/).textContent)).toBe('R$ 1.250,00');
    expect(plain((await factCard('Já pago')).getByText(/0,10/).textContent)).toBe('R$ 0,10');
    expect(plain((await factCard('Total histórico')).getByText(/678,90/).textContent)).toBe('R$ 123.456.789.012.345.678,90');
    expect((await factCard('Contas em aberto')).getByText('7')).toBeInTheDocument();
  });

  it('fato sem valor mostra travessão e o motivo, nunca zero', async () => {
    mount('/ai?run=run-0001');
    const card = await factCard('Vencido');
    expect(card.getByText('—')).toBeInTheDocument();
    expect(card.getByText('Sem valor: Nenhuma conta deste período tem vencimento cadastrado.')).toBeInTheDocument();
    expect(card.queryByText(/R\$/)).not.toBeInTheDocument();
    expect(card.queryByText(/0,00/)).not.toBeInTheDocument();
  });

  it('cada fato informa período, escopo e de onde veio', async () => {
    mount('/ai?run=run-0001');
    const card = await factCard('Falta pagar');
    expect(card.getByText('outubro/2026')).toBeInTheDocument();
    expect(card.getByText('Pessoal · competência mensal')).toBeInTheDocument();
    expect(card.getByText('Contas a pagar de outubro/2026')).toBeInTheDocument();
    expect(card.getByText('01/10/2026 às 09:00')).toBeInTheDocument();

    const sources = within(screen.getByRole('heading', { name: 'Fontes' }).parentElement!);
    expect(sources.getByText('Contas a pagar de outubro/2026')).toBeInTheDocument();
    expect(sources.getByText('sql:payables:2026-10')).toBeInTheDocument();
    expect(sources.getByText(/Dados do aplicativo/)).toBeInTheDocument();
  });

  it('avisa em linguagem simples quando houve fallback de modelo', async () => {
    api.getRun.mockResolvedValue({ ...QUESTION_DONE, model: { alias: 'local-texto-b', provider: 'ollama', fallback_used: true }, warnings: ['A resposta levou mais tempo que o normal.'] });
    mount('/ai?run=run-0001');
    const note = await screen.findByRole('note');
    expect(note).toHaveTextContent('O modelo preferido não respondeu, então esta resposta foi preparada por um modelo alternativo (local-texto-b).');
    expect(note).toHaveTextContent('A resposta levou mais tempo que o normal.');
  });

  it('sem fallback não há aviso de degradação', async () => {
    mount('/ai?run=run-0001');
    await screen.findByText('Execução concluída.');
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });

  it('rastrear mostra código de rastreio, execução, etapas e modelo', async () => {
    mount('/ai?run=run-0001');
    await screen.findByText('Execução concluída.');
    const toggle = runPanel().getByRole('button', { name: 'Rastrear' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');

    const trace = within(screen.getByRole('region', { name: 'Rastreio' }));
    expect(trace.getByText('rastreio-0001')).toBeInTheDocument();
    expect(trace.getByText('run-0001')).toBeInTheDocument();
    expect(trace.getByText('local-texto-a (ollama)')).toBeInTheDocument();
    expect(trace.getByText('1. Consultando contas a pagar')).toBeInTheDocument();
    expect(trace.getByText('2. Redigindo a resposta')).toBeInTheDocument();
  });
});

describe('proposta', () => {
  beforeEach(() => { api.getRun.mockResolvedValue(WAITING_PAYMENT); });

  it('baixa parcial mostra antes e depois de pago, restante e situação', async () => {
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    const table = within(card.getByRole('table', { name: 'Impacto: antes e depois de aplicar' }));
    expect(rowCells(table, 'Pago')).toEqual(['R$ 0,00', 'R$ 100,00']);
    expect(rowCells(table, 'Restante')).toEqual(['R$ 300,00', 'R$ 200,00']);
    expect(rowCells(table, 'Situação')).toEqual(['Pendente', 'Parcial']);
    expect(card.getByText('Conta corrente fictícia')).toBeInTheDocument();
    expect(card.getByText('Casa')).toBeInTheDocument();
    expect(card.getByText('Pessoal')).toBeInTheDocument();
    expect(card.getByText(/Vale até 02\/10\/2099 às 09:00/)).toBeInTheDocument();
    expect(card.getByText('Pronta para revisão')).toBeInTheDocument();
    expect(card.queryByRole('note')).not.toBeInTheDocument();
    // O backend manda `items_new: 0`, `items_duplicate: 0` e `totals: {}` em toda baixa;
    // numa baixa isso não é informação e não pode aparecer como "Itens novos: 0".
    expect(card.queryByText(/Itens novos|Duplicados|Transferências/)).not.toBeInTheDocument();
  });

  it('importação mostra origem, período, itens novos, duplicados, totais e destaca ambiguidades', async () => {
    api.getRun.mockResolvedValue(WAITING_IMPORT);
    api.getProposal.mockResolvedValue(IMPORT_PROPOSAL);
    mount('/ai?run=run-0002');
    const card = await proposalCard('Importação de extrato');

    expect(card.getByText(/extrato-setembro-ficticio\.ofx/)).toBeInTheDocument();
    expect(card.getByText('01/09/2026 a 30/09/2026')).toBeInTheDocument();
    const pair = (term: string) => pairIn(card, term);
    expect(pair('Itens novos')).toBe('42');
    expect(pair('Duplicados (não serão importados)')).toBe('3');
    expect(pair('Transferências (não serão importadas)')).toBe('1');
    // Chaves que o backend emite de verdade: income, expense, net e transfer_skipped.
    expect(pair('Entradas')).toBe('R$ 5.200,00');
    expect(pair('Saídas')).toBe('R$ 4.310,75');
    expect(pair('Saldo do período')).toBe('R$ 889,25');
    expect(pair('Transferências não importadas')).toBe('R$ 500,00');
    // Nenhum nome de campo cru chega ao titular.
    expect(screen.getByRole('article').textContent).not.toMatch(/income|expense|transfer.skipped|Outro total/i);

    const ambiguities = card.getByRole('note');
    expect(ambiguities).toHaveTextContent('2 pontos ambíguos precisam da sua revisão');
    expect(ambiguities).toHaveTextContent('1 transferência(s), no total de R$ 500,00, não serão importadas: o extrato não informa a conta de destino.');
    expect(ambiguities).toHaveTextContent('4 transações ficaram sem categoria sugerida.');
    expect(ambiguities).not.toHaveTextContent('Impede a aprovação');
    expect(card.getByText('email:mensagem-ficticia-0001')).toBeInTheDocument();
    expect(card.getByText('artifact:arquivo-ficticio-0001')).toBeInTheDocument();
    expect(card.getByText('Importado')).toBeInTheDocument();
  });

  it('aprovar descreve o efeito, envia hash e versão e bloqueia duplo envio', async () => {
    api.getRun.mockImplementation(async id => (id === 'run-0003' ? APPLIED_RUN : WAITING_PAYMENT));
    const approval = deferred<RunAccepted>();
    api.approveProposal.mockImplementation(() => {
      // Depois da aprovação o servidor passa a devolver a proposta já aplicada.
      api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id });
      return approval.promise;
    });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    await userEvent.click(card.getByRole('button', { name: 'Aprovar' }));

    const dialog = within(screen.getByRole('dialog', { name: 'Aprovar proposta' }));
    expect(dialog.getByRole('button', { name: 'Cancelar' })).toHaveFocus();
    const text = plain(screen.getByRole('dialog').textContent);
    expect(text).toContain('de R$ 0,00 para R$ 100,00');
    expect(text).toContain('de R$ 300,00 para R$ 200,00');
    expect(text).toContain('de Pendente para Parcial');
    expect(text).toContain('Ao aprovar, o aplicativo registra este pagamento na conta a pagar.');
    expect(text).toContain('Nenhum dinheiro é movimentado no banco.');
    expect(dialog.getByText('Registrado pago')).toBeInTheDocument();

    const confirm = dialog.getByRole('button', { name: 'Aprovar e aplicar' });
    fireEvent.click(confirm); fireEvent.click(confirm);
    expect(api.approveProposal).toHaveBeenCalledExactlyOnceWith(PAYMENT_PROPOSAL.proposal_id, { payload_hash: PAYMENT_PROPOSAL.payload_hash, version: 3 });
    expect(dialog.getByRole('button', { name: 'Confirmando…' })).toBeDisabled();

    await act(async () => approval.resolve({ run_id: 'run-0003', status: 'queued', trace_id: 'rastreio-0003' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(api.getRun).toHaveBeenCalledWith('run-0003', expect.anything()));
    expect(api.approveProposal).toHaveBeenCalledOnce();

    // A execução de aplicação termina e a tela mostra o que foi gravado.
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    expect(applied.getByText('Gravada')).toBeInTheDocument();
    expect(applied.getByText(PAYMENT_OPERATION.operation_id)).toBeInTheDocument();
    expect(stageItem('Aplicado')).toHaveTextContent('concluída');
    // A prévia foi buscada de novo: não fica um "Aprovar" ativo de uma proposta já aplicada.
    const after = await proposalCard('Baixa em conta a pagar');
    await waitFor(() => expect(after.getByText('Aplicada')).toBeInTheDocument());
    expect(after.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument();
    expect(api.getProposal).toHaveBeenCalledTimes(2);
  });

  it('cancelar a confirmação não grava nada e devolve o foco ao botão', async () => {
    mount('/ai?run=run-0001');
    const approve = (await proposalCard('Baixa em conta a pagar')).getByRole('button', { name: 'Aprovar' });
    await userEvent.click(approve);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(api.approveProposal).not.toHaveBeenCalled();
    expect(approve).toHaveFocus();
  });

  it('proposta desatualizada: mostra a mensagem segura com o rastreio e recarrega a prévia', async () => {
    api.approveProposal.mockRejectedValue(apiError({ code: 'stale_proposal', retryable: false, status: 409, safeMessage: 'A proposta ficou desatualizada. Gere uma nova prévia.', traceId: 'rastreio-0409' }));
    mount('/ai?run=run-0001');
    await userEvent.click((await proposalCard('Baixa em conta a pagar')).getByRole('button', { name: 'Aprovar' }));
    expect(api.getProposal).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole('button', { name: 'Aprovar e aplicar' }));

    const alert = await within(screen.getByRole('dialog')).findByRole('alert');
    expect(alert).toHaveTextContent('A proposta ficou desatualizada. Gere uma nova prévia.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0409');
    await waitFor(() => expect(api.getProposal).toHaveBeenCalledTimes(2));
  });

  it('escrita desligada no servidor: revisa, mas não aprova', async () => {
    api.getStatus.mockResolvedValue({ ...STATUS_SINGLE_SPACE, flags: { cloud: false, email: true, write: false } });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    expect(card.getByRole('button', { name: 'Aprovar' })).toBeDisabled();
    expect(card.getByText(/gravação pelo operador está desativada/)).toBeInTheDocument();
    expect(card.getByRole('button', { name: 'Corrigir' })).toBeEnabled();
  });

  it('proposta já decidida não oferece aprovar nem corrigir', async () => {
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'rejected' });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    expect(card.getByText('Rejeitada')).toBeInTheDocument();
    expect(card.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument();
    expect(card.queryByRole('button', { name: 'Corrigir' })).not.toBeInTheDocument();
    expect(card.getByRole('button', { name: 'Rastrear' })).toBeInTheDocument();
  });

  it('corrigir rejeita com o motivo e devolve o pedido preenchido ao formulário', async () => {
    mount();
    await fillAndSend('Registrar pagamento de 100 reais na conta de internet');
    const card = await proposalCard('Baixa em conta a pagar');
    await userEvent.click(card.getByRole('button', { name: 'Corrigir' }));

    const dialog = within(screen.getByRole('dialog', { name: 'Corrigir proposta' }));
    const reason = dialog.getByLabelText('O que precisa ser corrigido?');
    expect(reason).toHaveFocus();
    // Sem motivo não há rejeição: o motivo vai para a auditoria.
    await userEvent.click(dialog.getByRole('button', { name: 'Rejeitar e refazer o pedido' }));
    expect(api.rejectProposal).not.toHaveBeenCalled();

    fireEvent.change(reason, { target: { value: 'O valor certo é 150 reais' } });
    await userEvent.click(dialog.getByRole('button', { name: 'Rejeitar e refazer o pedido' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.rejectProposal).toHaveBeenCalledExactlyOnceWith(PAYMENT_PROPOSAL.proposal_id, 'O valor certo é 150 reais');
    const field = await messageField();
    expect(field).toHaveValue('Registrar pagamento de 100 reais na conta de internet\n\nCorreção: O valor certo é 150 reais');
    await waitFor(() => expect(field).toHaveFocus());
    expect(api.approveProposal).not.toHaveBeenCalled();
  });

  it('rastrear a partir da proposta mostra versão e hash do conteúdo', async () => {
    mount('/ai?run=run-0001');
    await userEvent.click((await proposalCard('Baixa em conta a pagar')).getByRole('button', { name: 'Rastrear' }));
    const trace = within(screen.getByRole('region', { name: 'Rastreio' }));
    expect(trace.getByText(PAYMENT_PROPOSAL.payload_hash)).toBeInTheDocument();
    expect(trace.getByText(PAYMENT_PROPOSAL.proposal_id)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Rastreio' })).toHaveFocus());
  });
});

describe('conferido, registrado pago e conciliado no extrato', () => {
  it('cada proposta mostra só o seu estado, com rótulo em texto', async () => {
    const byId: Record<string, AiProposal> = {
      'p-conferido': { ...PAYMENT_PROPOSAL, proposal_id: 'p-conferido', effect: { ...PAYMENT_PROPOSAL.effect, state_after: 'conferido' } },
      'p-registrado': { ...PAYMENT_PROPOSAL, proposal_id: 'p-registrado', effect: { ...PAYMENT_PROPOSAL.effect, state_after: 'registrado_pago' } },
      'p-conciliado': { ...PAYMENT_PROPOSAL, proposal_id: 'p-conciliado', effect: { ...PAYMENT_PROPOSAL.effect, state_after: 'conciliado' } },
    };
    api.getRun.mockResolvedValue(makeRun({ status: 'waiting_review', progress: { stage: 'waiting_review', steps: [] }, proposal_ids: Object.keys(byId) }));
    api.getProposal.mockImplementation(async id => byId[id]);
    mount('/ai?run=run-0001');

    const cards = await screen.findAllByRole('article');
    expect(cards).toHaveLength(3);
    const labels = ['Conferido', 'Registrado pago', 'Conciliado no extrato'];
    cards.forEach((card, index) => {
      labels.forEach((label, position) => {
        const found = within(card).queryByText(label);
        if (position === index) expect(found).toBeInTheDocument();
        else expect(found).not.toBeInTheDocument();
      });
    });
  });

  it('explica a diferença entre os três em texto curto', async () => {
    api.getRun.mockResolvedValue(WAITING_PAYMENT);
    mount('/ai?run=run-0001');
    const legend = within(await screen.findByRole('region', { name: 'Três estados que não são a mesma coisa' }));
    const explanation = (label: string) => legend.getByText(label).closest('div')!.querySelector('dd')!.textContent;
    expect(explanation('Conferido')).toMatch(/não é baixa/);
    expect(explanation('Registrado pago')).toMatch(/sem vínculo com o extrato do banco/);
    expect(explanation('Conciliado no extrato')).toMatch(/transação que veio do extrato do banco/);
    expect(new Set(['Conferido', 'Registrado pago', 'Conciliado no extrato'].map(explanation)).size).toBe(3);
  });
});

describe('resultado aplicado e desfazer', () => {
  beforeEach(() => {
    api.getRun.mockResolvedValue(APPLIED_RUN);
    api.getProposal.mockImplementation(async id => (id === REVERSAL_PROPOSAL.proposal_id ? REVERSAL_PROPOSAL : { ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id }));
  });

  it('mostra o que foi gravado, com a operação', async () => {
    mount('/ai?run=run-0003');
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    expect(applied.getByText(PAYMENT_OPERATION.operation_id)).toBeInTheDocument();
    expect(applied.getByText('Pagamento parcial de R$ 100,00 registrado na conta "Internet fibra".')).toBeInTheDocument();
    expect(applied.getByText('Registrado pago')).toBeInTheDocument();
    expect(applied.getByText('01/10/2026 às 09:05 (horário de Brasília)')).toBeInTheDocument();
    const table = within(applied.getByRole('table', { name: 'O que foi gravado: antes e depois' }));
    expect(table.getByRole('columnheader', { name: 'Gravado' })).toBeInTheDocument();
    expect(api.getOperation).toHaveBeenCalledWith(PAYMENT_OPERATION.operation_id, expect.anything());
  });

  it('desfazer pede motivo e cria uma proposta de compensação que ainda precisa de aprovação', async () => {
    api.reverseOperation.mockResolvedValue({ proposal_id: REVERSAL_PROPOSAL.proposal_id });
    mount('/ai?run=run-0003');
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    await userEvent.click(applied.getByRole('button', { name: 'Desfazer' }));

    const dialog = within(screen.getByRole('dialog', { name: 'Desfazer operação' }));
    fireEvent.change(dialog.getByLabelText('Por que desfazer?'), { target: { value: 'Lançado na conta errada' } });
    const submit = dialog.getByRole('button', { name: 'Criar proposta de compensação' });
    act(() => { submit.click(); submit.click(); });

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.reverseOperation).toHaveBeenCalledExactlyOnceWith(PAYMENT_OPERATION.operation_id, 'Lançado na conta errada');
    const compensation = within(await screen.findByRole('article', { name: 'Proposta: Compensação (desfazer)' }));
    expect(compensation.getByRole('button', { name: 'Aprovar' })).toBeEnabled();
    expect(compensation.getByText('Desfeito')).toBeInTheDocument();
    expect(screen.getByText(/Nada foi desfeito ainda/)).toBeInTheDocument();
    expect(api.approveProposal).not.toHaveBeenCalled();
  });

  it('operação já desfeita não oferece desfazer de novo', async () => {
    api.getOperation.mockResolvedValue({ ...PAYMENT_OPERATION, status: 'reversed', reversed_at: '2026-10-01T13:00:00Z', reversed_by_operation_id: 'operacao-0002' });
    mount('/ai?run=run-0003');
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    expect(applied.getByText('Desfeita')).toBeInTheDocument();
    expect(applied.queryByRole('button', { name: 'Desfazer' })).not.toBeInTheDocument();
  });
});

describe('erros', () => {
  it('mostra a mensagem segura e o código de rastreio', async () => {
    api.createRun.mockRejectedValue(apiError());
    mount();
    await fillAndSend('Quanto falta pagar em outubro?');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('O pedido não foi enviado.');
    expect(alert).toHaveTextContent('Nenhum modelo autorizado está disponível agora.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0503');
  });

  it('nunca mostra o erro técnico cru', async () => {
    api.createRun.mockRejectedValue(Object.assign(new Error('Request failed with status code 500'), {
      response: { status: 500, data: '<html>Traceback (most recent call last): KeyError</html>' },
      config: { url: '/api/ai/v1/runs', headers: { 'X-CSRF-Token': 'csrf-de-teste' } },
    }));
    mount();
    await fillAndSend('Quanto falta pagar em outubro?');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível concluir o pedido.');
    expect(document.body.textContent).not.toMatch(/Request failed|status code|Traceback|KeyError|csrf-de-teste|\/api\/ai/);
  });

  it('reenvio do mesmo pedido reutiliza a mesma Idempotency-Key', async () => {
    api.createRun.mockRejectedValueOnce(apiError());
    mount();
    await fillAndSend('Quanto falta pagar em outubro?');
    await screen.findByRole('alert');
    await userEvent.click(sendButton());
    await screen.findByRole('region', { name: 'Andamento' });

    expect(api.createRun).toHaveBeenCalledTimes(2);
    const [first, second] = api.createRun.mock.calls;
    expect(second[0]).toEqual(first[0]);
    expect(first[1].idempotencyKey).toMatch(/^[0-9a-f-]{36}$/);
    expect(second[1].idempotencyKey).toBe(first[1].idempotencyKey);

    // Depois de aceito, um novo pedido é outra intenção: outra chave.
    await fillAndSend('Quanto falta pagar em outubro?');
    await waitFor(() => expect(api.createRun).toHaveBeenCalledTimes(3));
    expect(api.createRun.mock.calls[2][1].idempotencyKey).not.toBe(first[1].idempotencyKey);
  });

  it('pedido editado depois da falha é outra intenção e ganha outra chave', async () => {
    api.createRun.mockRejectedValueOnce(apiError());
    mount();
    await fillAndSend('Quanto falta pagar em outubro?');
    await screen.findByRole('alert');
    await fillAndSend('Quanto falta pagar em novembro?');
    await waitFor(() => expect(api.createRun).toHaveBeenCalledTimes(2));
    const [first, second] = api.createRun.mock.calls;
    expect(second[1].idempotencyKey).not.toBe(first[1].idempotencyKey);
  });

  it('execução que falhou mostra a mensagem segura e o rastreio do servidor', async () => {
    api.getRun.mockResolvedValue(makeRun({
      status: 'failed', progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo', 'failed', 'email.download_attachment')] },
      error: { code: 'connector_unavailable', retryable: true, safe_message: 'O conector necessário está indisponível.', trace_id: 'rastreio-0077' },
    }));
    mount('/ai?run=run-0001');
    await screen.findByText('A execução falhou.');
    const alert = runPanel().getByRole('alert');
    expect(alert).toHaveTextContent('O conector necessário está indisponível.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0077');
    expect(stageItem('Lendo')).toHaveTextContent('falhou');
  });

  it('falha ao carregar a proposta mostra o erro com rastreio e permite tentar novamente', async () => {
    api.getRun.mockResolvedValue(WAITING_PAYMENT);
    api.getProposal.mockRejectedValueOnce(apiError({ traceId: 'rastreio-0700' }));
    mount('/ai?run=run-0001');
    const section = within(await screen.findByRole('region', { name: 'Proposta para revisão' }));
    const alert = await section.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar a proposta.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0700');
    expect(section.queryByRole('article')).not.toBeInTheDocument();

    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    expect(await section.findByRole('article', { name: 'Proposta: Baixa em conta a pagar' })).toBeInTheDocument();
    expect(section.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('falha ao carregar o que foi gravado não some da tela', async () => {
    api.getRun.mockResolvedValue(APPLIED_RUN);
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id });
    api.getOperation.mockRejectedValue(apiError({ traceId: 'rastreio-0701' }));
    mount('/ai?run=run-0003');
    const section = within(await screen.findByRole('region', { name: 'Resultado aplicado' }));
    const alert = await section.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível carregar o que foi gravado.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0701');
  });

  it('falha ao acompanhar preserva o último estado e oferece tentar novamente', async () => {
    api.getRun.mockResolvedValueOnce(makeRun({ status: 'running', progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo', 'started')] } }));
    api.getRun.mockRejectedValue(apiError({ code: 'not_found', retryable: false, status: 404, safeMessage: 'Recurso não encontrado.', traceId: 'rastreio-0404' }));
    mount('/ai?run=run-0001');
    await screen.findByRole('region', { name: 'Andamento' });
    const alert = await runPanel().findByRole('alert');
    expect(alert).toHaveTextContent('Recurso não encontrado.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0404');
    // O andamento já conhecido continua na tela.
    expect(stageItem('Lendo')).toHaveTextContent('em andamento');

    api.getRun.mockResolvedValue(QUESTION_DONE);
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    await screen.findByText('Execução concluída.');
    expect(runPanel().queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('estados da tela', () => {
  const expectNoRedirect = () => {
    expect(screen.queryByText('TELA DE LOGIN')).not.toBeInTheDocument();
    expect(screen.queryByText('OUTRA TELA')).not.toBeInTheDocument();
  };
  const expectNoRequests = () => {
    expect(api.createRun).not.toHaveBeenCalled();
    expect(api.listRuns).not.toHaveBeenCalled();
    expect(api.getRun).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Seu pedido')).not.toBeInTheDocument();
  };

  it('carregando', async () => {
    api.getStatus.mockImplementation(() => new Promise(() => {}));
    mount();
    expect(screen.getByRole('status')).toHaveTextContent('Verificando o operador…');
    expectNoRequests();
  });

  it('IA desativada explica e não desloga', async () => {
    api.getStatus.mockResolvedValue({ ...STATUS_SINGLE_SPACE, enabled: false });
    mount('/ai?run=run-0001');
    expect(await screen.findByRole('heading', { name: 'O operador está desativado' })).toBeInTheDocument();
    expect(screen.getByText(/O restante do aplicativo continua funcionando normalmente/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Contas a pagar' })).toHaveAttribute('href', '/financial-expenses');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expectNoRedirect(); expectNoRequests();
  });

  it('503 com ai_disabled também vira o estado desativado', async () => {
    api.getStatus.mockRejectedValue(apiError({ code: 'ai_disabled', retryable: false, status: 503, safeMessage: 'O operador de IA está desativado.' }));
    mount();
    expect(await screen.findByRole('heading', { name: 'O operador está desativado' })).toBeInTheDocument();
    expectNoRedirect(); expectNoRequests();
  });

  it('sessão do novo backend ausente (401) explica e não desloga', async () => {
    api.getStatus.mockRejectedValue(apiError({ code: 'unauthorized', retryable: false, status: 401, safeMessage: 'Sessão ausente ou expirada.' }));
    mount();
    expect(await screen.findByRole('heading', { name: 'Falta iniciar a sessão do operador' })).toBeInTheDocument();
    expect(screen.getByText(/Você continua conectado ao Alça Finanças/)).toBeInTheDocument();
    expect(screen.getByText(/O restante do aplicativo continua funcionando normalmente/)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expectNoRedirect(); expectNoRequests();
  });

  it('sem autorização (403) explica e não desloga', async () => {
    api.getStatus.mockRejectedValue(apiError({ code: 'capability_denied', retryable: false, status: 403, safeMessage: 'Esta capacidade não está autorizada.' }));
    mount();
    expect(await screen.findByRole('heading', { name: 'Seu usuário não tem autorização para o operador' })).toBeInTheDocument();
    expect(screen.getByText(/O restante do aplicativo continua funcionando normalmente/)).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expectNoRedirect(); expectNoRequests();
  });

  it('verificar novamente refaz a consulta e libera a tela quando a sessão existe', async () => {
    api.getStatus.mockRejectedValueOnce(apiError({ code: 'unauthorized', retryable: false, status: 401, safeMessage: 'Sessão ausente ou expirada.' }));
    mount();
    await userEvent.click(await screen.findByRole('button', { name: 'Verificar novamente' }));
    expect(await messageField()).toBeInTheDocument();
    expect(api.getStatus).toHaveBeenCalledTimes(2);
  });

  it('sessão perdida no meio do uso leva ao estado explicado, sem redirecionar', async () => {
    api.createRun.mockRejectedValue(apiError({ code: 'unauthorized', retryable: false, status: 401, safeMessage: 'Sessão ausente ou expirada.' }));
    mount();
    await messageField();
    api.getStatus.mockRejectedValue(apiError({ code: 'unauthorized', retryable: false, status: 401, safeMessage: 'Sessão ausente ou expirada.' }));
    await fillAndSend('Quanto falta pagar em outubro?');
    expect(await screen.findByRole('heading', { name: 'Falta iniciar a sessão do operador' })).toBeInTheDocument();
    expectNoRedirect();
  });

  it('erro ao verificar o operador mostra mensagem segura e tentar novamente', async () => {
    api.getStatus.mockRejectedValueOnce(apiError({ code: 'internal_error', status: 500, safeMessage: 'Não foi possível concluir o pedido.', traceId: 'rastreio-0500' }));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Não foi possível verificar o operador.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0500');
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    expect(await messageField()).toBeInTheDocument();
  });

  it('vazio: sem execuções, convida a fazer o primeiro pedido', async () => {
    mount();
    expect(await screen.findByText('Nenhuma execução ainda. Faça um pedido para começar.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Andamento' })).not.toBeInTheDocument();
    expect(api.listRuns).toHaveBeenCalledWith({ financial_space_id: PERSONAL_SPACE.id, limit: 5 }, expect.anything());
  });

  it('histórico carregando não aparece como vazio', async () => {
    api.listRuns.mockImplementation(() => new Promise(() => {}));
    mount();
    const history = within(await screen.findByRole('region', { name: 'Execuções recentes' }));
    expect(history.getByRole('status')).toHaveTextContent('Carregando histórico…');
    expect(history.queryByText(/Nenhuma execução ainda/)).not.toBeInTheDocument();
  });

  it('falha no histórico não aparece como vazio e permite tentar novamente', async () => {
    api.listRuns.mockRejectedValueOnce(apiError({ traceId: 'rastreio-0900' }));
    mount();
    const history = within(await screen.findByRole('region', { name: 'Execuções recentes' }));
    const alert = await history.findByRole('alert');
    expect(alert).toHaveTextContent('Histórico indisponível.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0900');
    expect(history.queryByText(/Nenhuma execução ainda/)).not.toBeInTheDocument();

    api.listRuns.mockResolvedValue({ runs: [{ run_id: 'run-0005', status: 'completed', task: 'finance_question', created_at: '2026-10-01T12:00:00Z', summary_pt_br: 'Resumo sintético.' }], next_cursor: null });
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    expect(await history.findByText('Resumo sintético.')).toBeInTheDocument();
    expect(history.getByText('Concluída')).toBeInTheDocument();
  });

  it('histórico abre uma execução anterior', async () => {
    api.listRuns.mockResolvedValue({ runs: [{ run_id: 'run-0005', status: 'completed', task: 'finance_question', created_at: '2026-10-01T12:00:00Z' }], next_cursor: null });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /Abrir execução: Pergunta sobre finanças/ }));
    await waitFor(() => expect(api.getRun).toHaveBeenCalledWith('run-0005', expect.anything()));
    await screen.findByText('Execução concluída.');
  });

  it('retoma sozinha a execução que ainda aguarda revisão', async () => {
    api.listRuns.mockResolvedValue({ runs: [
      { run_id: 'run-0006', status: 'completed', task: 'finance_question', created_at: '2026-10-01T12:10:00Z' },
      { run_id: 'run-0001', status: 'waiting_review', task: 'finance_question', created_at: '2026-10-01T12:00:00Z' },
    ], next_cursor: null });
    api.getRun.mockResolvedValue(WAITING_PAYMENT);
    mount();
    await screen.findByText('Aguardando a sua revisão.');
    expect(api.getRun).toHaveBeenCalledWith('run-0001', expect.anything());
    expect(api.getRun).not.toHaveBeenCalledWith('run-0006', expect.anything());
  });
});

describe('espaço financeiro e privacidade', () => {
  it('com um espaço mostra o nome e se é pessoal ou negócio', async () => {
    mount();
    const context = within(await screen.findByRole('region', { name: 'Espaço financeiro e privacidade' }));
    expect(context.getByText('Casa')).toBeInTheDocument();
    expect(context.getByText('Pessoal')).toBeInTheDocument();
    expect(context.queryByRole('combobox')).not.toBeInTheDocument();
    expect(context.getByText(/Processamento local\./)).toBeInTheDocument();
    expect(context.getByText(/não são enviados a serviços externos de IA/)).toBeInTheDocument();
  });

  it('com mais de um espaço oferece seletor e envia o espaço escolhido', async () => {
    api.getStatus.mockResolvedValue(STATUS_READY);
    mount();
    const context = within(await screen.findByRole('region', { name: 'Espaço financeiro e privacidade' }));
    const select = context.getByRole('combobox', { name: 'Espaço financeiro em uso' });
    expect(within(select).getAllByRole('option').map(option => option.textContent)).toEqual(['Casa — Pessoal', 'Marketing digital — Negócio']);
    expect(context.getByText('Pessoal', { selector: '.ai-badge' })).toBeInTheDocument();

    await userEvent.selectOptions(select, BUSINESS_SPACE.id);
    expect(context.getByText('Negócio', { selector: '.ai-badge' })).toBeInTheDocument();
    await waitFor(() => expect(api.listRuns).toHaveBeenCalledWith({ financial_space_id: BUSINESS_SPACE.id, limit: 5 }, expect.anything()));

    await fillAndSend('Quanto entrou de comissão em setembro?');
    await waitFor(() => expect(api.createRun).toHaveBeenCalledWith(expect.objectContaining({ financial_space_id: BUSINESS_SPACE.id }), expect.anything()));
  });

  it('busca no e-mail desativada no servidor fica indisponível na tela', async () => {
    api.getStatus.mockResolvedValue({ ...STATUS_SINGLE_SPACE, flags: { cloud: false, email: false, write: true } });
    mount();
    expect(await screen.findByRole('radio', { name: /Buscar extrato no e-mail/ })).toBeDisabled();
    expect(screen.getByText('A busca no e-mail está desativada no servidor.')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Pergunta sobre finanças/ })).toBeChecked();
  });

  it('sem espaço financeiro explica e não oferece o formulário', async () => {
    api.getStatus.mockResolvedValue({ ...STATUS_SINGLE_SPACE, spaces: [] });
    mount();
    expect(await screen.findByText(/Nenhum espaço financeiro está vinculado ao seu usuário/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Seu pedido')).not.toBeInTheDocument();
    expect(api.listRuns).not.toHaveBeenCalled();
  });
});

describe('proposta: formas que o backend emite', () => {
  beforeEach(() => { api.getRun.mockResolvedValue(WAITING_PAYMENT); });

  it('compensação de baixa mostra o estado "Desfeito", no cartão e no diálogo de aprovação', async () => {
    api.getProposal.mockResolvedValue(REVERSAL_PROPOSAL);
    mount('/ai?run=run-0001');
    const card = await proposalCard('Compensação (desfazer)');
    expect(card.getByText('Desfeito')).toBeInTheDocument();
    const table = within(card.getByRole('table', { name: 'Impacto: antes e depois de aplicar' }));
    expect(rowCells(table, 'Pago')).toEqual(['R$ 100,00', 'R$ 0,00']);
    expect(rowCells(table, 'Situação')).toEqual(['Parcial', 'Pendente']);
    expect(card.queryByText(/Itens novos|Duplicados|Lançamentos que serão cancelados/)).not.toBeInTheDocument();

    await userEvent.click(card.getByRole('button', { name: 'Aprovar' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Aprovar proposta' }));
    expect(dialog.getByText('Desfeito')).toBeInTheDocument();
    expect(plain(screen.getByRole('dialog').textContent)).toContain('Ao aprovar, o aplicativo grava uma compensação que desfaz a operação original.');
    expect(document.body.textContent).not.toContain('Estado não informado');
  });

  it('compensação de importação diz quantos lançamentos serão cancelados, não "itens novos"', async () => {
    api.getProposal.mockResolvedValue(IMPORT_REVERSAL_PROPOSAL);
    mount('/ai?run=run-0001');
    const card = await proposalCard('Compensação (desfazer)');
    expect(pairIn(card, 'Lançamentos que serão cancelados')).toBe('42');
    expect(pairIn(card, 'Entradas')).toBe('R$ 5.200,00');
    expect(pairIn(card, 'Saldo do período')).toBe('R$ 889,25');
    expect(card.getByText('Desfeito')).toBeInTheDocument();
    expect(card.queryByText('Itens novos')).not.toBeInTheDocument();
    expect(card.queryByText(/Duplicados/)).not.toBeInTheDocument();
  });

  it('o diálogo de aprovação de uma importação repete itens e totais da prévia', async () => {
    api.getRun.mockResolvedValue(WAITING_IMPORT);
    api.getProposal.mockResolvedValue(IMPORT_PROPOSAL);
    mount('/ai?run=run-0002');
    await userEvent.click((await proposalCard('Importação de extrato')).getByRole('button', { name: 'Aprovar' }));
    const dialog = screen.getByRole('dialog', { name: 'Aprovar proposta' });
    const detail = (term: string) => plain(within(dialog).getByText(term).nextElementSibling!.textContent);
    expect(detail('Itens novos')).toBe('42');
    expect(detail('Duplicados (não serão importados)')).toBe('3');
    expect(detail('Entradas')).toBe('R$ 5.200,00');
    expect(detail('Saídas')).toBe('R$ 4.310,75');
    expect(dialog).toHaveTextContent('esta proposta tem 2 pontos ambíguos');
    expect(within(dialog).getByText('Importado')).toBeInTheDocument();
  });

  it('total que é contagem aparece como número; total ausente vira travessão', async () => {
    api.getRun.mockResolvedValue(WAITING_IMPORT);
    api.getProposal.mockResolvedValue({ ...IMPORT_PROPOSAL, effect: { ...IMPORT_PROPOSAL.effect, totals: { income: '5200.00', count: '3', categorias_novas: 2, net: null } } });
    mount('/ai?run=run-0002');
    const card = await proposalCard('Importação de extrato');
    expect(pairIn(card, 'Entradas')).toBe('R$ 5.200,00');
    // "3" é uma contagem: tratá-la como dinheiro mostraria "R$ 3,00".
    expect(pairIn(card, 'Itens')).toBe('3');
    expect(pairIn(card, 'Outro total (categorias novas)')).toBe('2');
    expect(pairIn(card, 'Saldo do período')).toBe('—');
  });

  it('valor ausente no antes/depois vira travessão, nunca zero, no cartão e no diálogo', async () => {
    api.getProposal.mockResolvedValue({
      ...PAYMENT_PROPOSAL,
      summary_pt_br: 'Registrar pagamento na conta "Internet fibra".',
      effect: { state_after: 'registrado_pago', before: { paid: null, remaining: null, status: null }, after: { paid: '100.00' }, items_new: 0, items_duplicate: 0, totals: {} },
    });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    const table = within(card.getByRole('table', { name: 'Impacto: antes e depois de aplicar' }));
    expect(rowCells(table, 'Pago')).toEqual(['—', 'R$ 100,00']);
    expect(rowCells(table, 'Restante')).toEqual(['—', '—']);
    expect(rowCells(table, 'Situação')).toEqual(['—', '—']);
    expect(plain(screen.getByRole('article').textContent)).not.toContain('R$ 0,00');

    await userEvent.click(card.getByRole('button', { name: 'Aprovar' }));
    const text = plain(screen.getByRole('dialog').textContent);
    expect(text).toContain('de — para R$ 100,00');
    expect(text).toContain('de — para —');
    expect(text).not.toContain('R$ 0,00');
  });
});

describe('proposta que não pode ser aprovada', () => {
  beforeEach(() => { api.getRun.mockResolvedValue(WAITING_PAYMENT); });

  it.each<[string, Partial<AiProposal>, string, RegExp]>([
    ['com a validade vencida, mesmo que o servidor ainda diga "ready"', { expires_at: '2020-01-01T12:00:00Z' }, 'Expirada', /expirou sem ser aplicada/],
    ['expirada', { status: 'expired' }, 'Expirada', /expirou sem ser aplicada/],
    ['desatualizada', { status: 'stale' }, 'Desatualizada', /Os dados mudaram depois que esta proposta foi preparada/],
  ])('%s: não oferece Aprovar nem Corrigir, só refazer o pedido', async (_case, overrides, badge, explanation) => {
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, ...overrides });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    expect(card.getByText(badge)).toBeInTheDocument();
    expect(card.getByText(explanation)).toBeInTheDocument();
    expect(card.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument();
    expect(card.queryByRole('button', { name: 'Corrigir' })).not.toBeInTheDocument();

    await userEvent.click(card.getByRole('button', { name: 'Refazer pedido' }));
    expect(screen.getByText(/O pedido voltou para o formulário/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText('Seu pedido')).toHaveFocus());
    expect(api.approveProposal).not.toHaveBeenCalled();
    expect(api.rejectProposal).not.toHaveBeenCalled();
  });

  it('validade vencida mostra quando expirou', async () => {
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, expires_at: '2020-01-01T12:00:00Z' });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    expect(card.getByText(/Expirou em 01\/01\/2020 às 09:00/)).toBeInTheDocument();
    expect(card.queryByText(/Vale até/)).not.toBeInTheDocument();
  });

  it('rascunho com pendência impeditiva: Aprovar fica desabilitado e a tela explica o que fazer', async () => {
    api.getProposal.mockResolvedValue({
      ...PAYMENT_PROPOSAL, status: 'draft', requires_review: true,
      ambiguities: [{ code: 'amount_mismatch', message: 'O valor do comprovante difere do valor da conta.', blocking: true }],
    });
    mount('/ai?run=run-0001');
    const card = await proposalCard('Baixa em conta a pagar');
    expect(card.getByText('Rascunho')).toBeInTheDocument();
    const approve = card.getByRole('button', { name: 'Aprovar' });
    expect(approve).toBeDisabled();
    expect(card.getByText(/tem pendências que impedem a aprovação/)).toBeInTheDocument();
    expect(card.getByRole('note')).toHaveTextContent('Impede a aprovação: O valor do comprovante difere do valor da conta.');

    fireEvent.click(approve);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(api.approveProposal).not.toHaveBeenCalled();
    // A saída de um rascunho é corrigir o pedido (rejeita e gera nova prévia).
    expect(card.getByRole('button', { name: 'Corrigir' })).toBeEnabled();
  });
});

describe('depois de aprovar', () => {
  const APPLIED_SAME_RUN = makeRun({
    status: 'completed', finished_at: '2026-10-01T12:05:01Z',
    progress: { stage: 'done', steps: [step(1, 'Preparando a baixa', 'succeeded', 'finance.prepare_change'), step(2, 'Gravando o pagamento', 'succeeded', 'finance.apply_change')] },
    proposal_ids: [PAYMENT_PROPOSAL.proposal_id], operation_ids: [PAYMENT_OPERATION.operation_id],
  });
  const approveAndConfirm = async () => {
    await userEvent.click((await proposalCard('Baixa em conta a pagar')).getByRole('button', { name: 'Aprovar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Aprovar e aplicar' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  };

  beforeEach(() => { api.getRun.mockResolvedValue(WAITING_PAYMENT); });

  // A spec promete o run_id da execução que aplica; o serviço de propostas devolve a
  // visão da proposta, com o run_id da execução de ORIGEM ou nulo. Nas duas formas a
  // tela não pode ficar parada em "aguardando revisão" com "Aprovar" ativo.
  it.each<[string, string | null]>([
    ['o run_id da execução que já está aberta', 'run-0001'],
    ['a visão da proposta, sem run_id', null],
  ])('servidor devolve %s: a tela reconsulta e mostra o que foi gravado', async (_case, runId) => {
    api.approveProposal.mockImplementation(async (): Promise<ApprovalAccepted> => {
      // A partir da aprovação o servidor passa a relatar a execução concluída e a proposta aplicada.
      api.getRun.mockResolvedValue(APPLIED_SAME_RUN);
      api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id });
      return { run_id: runId, status: 'approved', trace_id: null };
    });
    mount('/ai?run=run-0001');
    await screen.findByText('Aguardando a sua revisão.');
    expect(api.getRun).toHaveBeenCalledOnce();
    await approveAndConfirm();

    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    expect(applied.getByText('Gravada')).toBeInTheDocument();
    expect(runPanel().getByRole('status')).toHaveTextContent('Execução concluída.');
    const card = await proposalCard('Baixa em conta a pagar');
    await waitFor(() => expect(card.getByText('Aplicada')).toBeInTheDocument());
    expect(card.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument();
    // Uma única reconsulta da MESMA execução; nenhuma execução desconhecida foi aberta.
    expect(api.getRun).toHaveBeenCalledTimes(2);
    expect(api.getRun.mock.calls.every(call => call[0] === 'run-0001')).toBe(true);
    expect(api.approveProposal).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Andamento' })).toHaveFocus());
  });

  it('aprovada e ainda não aplicada: a prévia deixa de oferecer Aprovar e avisa que falta a gravação', async () => {
    api.approveProposal.mockImplementation(async (): Promise<ApprovalAccepted> => {
      api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'approved' });
      return { run_id: 'run-0001', status: 'approved', trace_id: null };
    });
    mount('/ai?run=run-0001');
    await approveAndConfirm();
    const card = await proposalCard('Baixa em conta a pagar');
    await waitFor(() => expect(card.getByText('Aprovada')).toBeInTheDocument());
    expect(card.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument();
    expect(card.queryByRole('button', { name: 'Corrigir' })).not.toBeInTheDocument();
    expect(card.getByText(/A gravação aparece em "Resultado aplicado" quando o servidor confirmar/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Resultado aplicado' })).not.toBeInTheDocument();

    // O servidor termina a gravação depois: "Atualizar" traz o estado novo sem recarregar a página.
    api.getRun.mockResolvedValue(APPLIED_SAME_RUN);
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id });
    await userEvent.click(runPanel().getByRole('button', { name: 'Atualizar' }));
    expect(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' })).toBeInTheDocument();
    await waitFor(() => expect(runPanel().getByRole('status')).toHaveTextContent('Execução concluída.'));
    expect(runPanel().queryByRole('button', { name: 'Atualizar' })).not.toBeInTheDocument();
  });

  it('gravação que termina depois, na mesma execução: a proposta acompanha até "Aplicada"', async () => {
    // O servidor aprova, passa a execução para "aplicando" e só então grava. Os ids da
    // execução e da proposta não mudam: a tela precisa reconsultar a proposta quando o
    // estado da execução muda, ou ficaria "Aprovada" ao lado da operação já gravada.
    let phase: 'ready' | 'approved' | 'applied' = 'ready';
    api.getProposal.mockImplementation(async () => (phase === 'applied'
      ? { ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id }
      : { ...PAYMENT_PROPOSAL, status: phase }));
    api.approveProposal.mockImplementation(async (): Promise<ApprovalAccepted> => {
      phase = 'approved';
      api.getRun
        .mockResolvedValueOnce(makeRun({ status: 'running', progress: { stage: 'applying', steps: [step(1, 'Gravando o pagamento', 'started', 'finance.apply_change')] }, proposal_ids: [PAYMENT_PROPOSAL.proposal_id] }))
        .mockImplementation(async () => { phase = 'applied'; return APPLIED_SAME_RUN; });
      return { run_id: 'run-0001', status: 'approved', trace_id: null };
    });
    mount('/ai?run=run-0001');
    await approveAndConfirm();

    await screen.findByText('Execução concluída.');
    const card = await proposalCard('Baixa em conta a pagar');
    await waitFor(() => expect(card.getByText('Aplicada')).toBeInTheDocument());
    expect(card.queryByText(/A gravação aparece em "Resultado aplicado"/)).not.toBeInTheDocument();
    expect(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' })).toBeInTheDocument();
    expect(stageItem('Aplicado')).toHaveTextContent('concluída');
  });

  it('abrir pelo histórico a execução que já está aberta reconsulta em vez de não fazer nada', async () => {
    api.listRuns.mockResolvedValue({ runs: [{ run_id: 'run-0001', status: 'waiting_review', task: 'finance_question', created_at: '2026-10-01T12:00:00Z' }], next_cursor: null });
    mount('/ai?run=run-0001');
    await proposalCard('Baixa em conta a pagar');
    expect(api.getRun).toHaveBeenCalledOnce();
    expect(api.getProposal).toHaveBeenCalledOnce();

    api.getRun.mockResolvedValue(APPLIED_SAME_RUN);
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id });
    await userEvent.click(screen.getByRole('button', { name: /Abrir execução: Pergunta sobre finanças/ }));
    await screen.findByText('Execução concluída.');
    expect(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' })).toBeInTheDocument();
  });

  it('sessão perdida ao aprovar leva ao estado explicado, sem redirecionar', async () => {
    api.getStatus.mockResolvedValueOnce(STATUS_SINGLE_SPACE).mockRejectedValue(UNAUTHORIZED());
    api.approveProposal.mockRejectedValue(UNAUTHORIZED());
    mount('/ai?run=run-0001');
    await userEvent.click((await proposalCard('Baixa em conta a pagar')).getByRole('button', { name: 'Aprovar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Aprovar e aplicar' }));

    expect(await screen.findByRole('heading', { name: 'Falta iniciar a sessão do operador' })).toBeInTheDocument();
    expect(within(screen.getByRole('dialog')).getByRole('alert')).toHaveTextContent('Sessão ausente ou expirada.');
    expect(api.getStatus).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('TELA DE LOGIN')).not.toBeInTheDocument();
  });
});

describe('regras de envio e de cancelamento', () => {
  const form = async () => (await messageField()).closest('form')!;

  it('execução em andamento bloqueia um novo pedido', async () => {
    api.getRun.mockResolvedValue(makeRun({ status: 'running', progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo', 'started')] } }));
    mount('/ai?run=run-0001');
    await screen.findByText('Lendo: Lendo o anexo.');
    fireEvent.change(await messageField(), { target: { value: 'Quais contas vencem nesta semana?' } });
    expect(sendButton()).toBeDisabled();
    expect(screen.getByText(/Há uma execução em andamento/)).toBeInTheDocument();
    // O formulário também pode ser enviado sem o botão; a regra vale do mesmo jeito.
    fireEvent.submit(await form());
    expect(api.createRun).not.toHaveBeenCalled();
  });

  it('em conferência (needs_reconciliation): não envia outro pedido, não oferece cancelar e segue acompanhando', async () => {
    const reconciling = makeRun({ run_id: 'run-0003', task: 'apply_proposal', status: 'needs_reconciliation', progress: { stage: 'applying', steps: [step(1, 'Gravando o pagamento', 'started', 'finance.apply_change')] }, proposal_ids: [PAYMENT_PROPOSAL.proposal_id] });
    const release = deferred<void>();
    // 1ª consulta: em conferência. A 2ª fica presa até `release`, para observar a tela
    // nesse estado; a 3ª já traz a gravação confirmada.
    api.getRun
      .mockResolvedValueOnce(reconciling)
      .mockImplementationOnce(async () => { await release.promise; return reconciling; })
      .mockResolvedValue(APPLIED_RUN);
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'approved' });
    mount('/ai?run=run-0003');
    await screen.findByText('Conferindo o resultado da gravação.');
    fireEvent.change(await messageField(), { target: { value: 'Quais contas vencem nesta semana?' } });
    expect(sendButton()).toBeDisabled();
    expect(screen.getByText(/O servidor ainda confere a última gravação/)).toBeInTheDocument();
    expect(screen.getByText(/Não repita o pedido/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument();
    fireEvent.submit(await form());
    expect(api.createRun).not.toHaveBeenCalled();

    // O acompanhamento não parou: quando o servidor confirma, a tela mostra o resultado.
    await act(async () => release.resolve());
    await screen.findByText('Execução concluída.');
    expect(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' })).toBeInTheDocument();
    expect(sendButton()).toBeEnabled();
  });

  it('aguardando revisão não oferece Cancelar (o servidor não cancela nesse estado) e diz como desistir', async () => {
    api.getRun.mockResolvedValue(WAITING_PAYMENT);
    mount('/ai?run=run-0001');
    await screen.findByText('Aguardando a sua revisão.');
    expect(runPanel().queryByRole('button', { name: 'Cancelar' })).not.toBeInTheDocument();
    expect(runPanel().getByText(/use "Corrigir" para rejeitar a proposta/)).toBeInTheDocument();
    expect((await proposalCard('Baixa em conta a pagar')).getByRole('button', { name: 'Corrigir' })).toBeEnabled();
    expect(api.cancelRun).not.toHaveBeenCalled();
  });

  it('cancelamento recusado mostra a mensagem segura e o código de rastreio', async () => {
    api.getRun.mockResolvedValue(makeRun({ status: 'running', progress: { stage: 'reading', steps: [step(1, 'Lendo o anexo', 'started')] } }));
    api.cancelRun.mockRejectedValue(apiError({ code: 'conflict', retryable: false, status: 409, safeMessage: 'A execução não pode mais ser cancelada.', traceId: 'rastreio-0410' }));
    mount('/ai?run=run-0001');
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar' }));
    const alert = await runPanel().findByRole('alert');
    expect(alert).toHaveTextContent('O cancelamento não foi confirmado.');
    expect(alert).toHaveTextContent('A execução não pode mais ser cancelada.');
    expect(alert).toHaveTextContent('Código de rastreio: rastreio-0410');
    // O andamento conhecido continua na tela e o botão volta a ficar disponível.
    expect(stageItem('Lendo')).toHaveTextContent('em andamento');
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeEnabled();
  });

  it('voltar ao texto original depois de editar reutiliza a chave do primeiro envio', async () => {
    api.createRun.mockRejectedValueOnce(apiError()).mockRejectedValueOnce(apiError());
    mount();
    const send = async (text: string, calls: number) => {
      await waitFor(() => expect(sendButton()).toBeEnabled());
      await fillAndSend(text);
      await waitFor(() => expect(api.createRun).toHaveBeenCalledTimes(calls));
    };
    // A resposta do 1º envio pode ter se perdido DEPOIS de o servidor criar a execução.
    await send('Quanto falta pagar em outubro?', 1);
    await send('Quanto falta pagar em novembro?', 2);
    await send('Quanto falta pagar em outubro?', 3);
    await screen.findByRole('region', { name: 'Andamento' });

    const keys = api.createRun.mock.calls.map(call => call[1].idempotencyKey);
    expect(keys[2]).toBe(keys[0]);
    expect(keys[1]).not.toBe(keys[0]);
    expect(api.createRun.mock.calls[2][0]).toEqual(api.createRun.mock.calls[0][0]);
  });

  it('e-mail desligado: refazer um pedido de extrato não sai como busca no e-mail', async () => {
    api.getStatus.mockResolvedValue({ ...STATUS_SINGLE_SPACE, flags: { cloud: false, email: false, write: true } });
    api.getRun.mockResolvedValue(WAITING_IMPORT);
    api.getProposal.mockResolvedValue({ ...IMPORT_PROPOSAL, status: 'stale' });
    mount('/ai?run=run-0002');
    await userEvent.click((await proposalCard('Importação de extrato')).getByRole('button', { name: 'Refazer pedido' }));

    // A opção desligada nunca fica marcada: marcada e desabilitada, ela seria enviada mesmo assim.
    expect(screen.getByRole('radio', { name: /Buscar extrato no e-mail/ })).toBeDisabled();
    expect(screen.getByRole('radio', { name: /Buscar extrato no e-mail/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /Pergunta sobre finanças/ })).toBeChecked();

    await fillAndSend('Buscar o extrato de setembro no e-mail');
    await waitFor(() => expect(api.createRun).toHaveBeenCalledOnce());
    expect(api.createRun.mock.calls[0][0].task).toBe('finance_question');
  });
});

describe('resultado aplicado: quando desfazer não é oferecido', () => {
  beforeEach(() => {
    api.getRun.mockResolvedValue(APPLIED_RUN);
    api.getProposal.mockResolvedValue({ ...PAYMENT_PROPOSAL, status: 'applied', operation_id: PAYMENT_OPERATION.operation_id });
  });

  it('uma compensação já é o desfazer de outra operação: não há desfazer em cadeia', async () => {
    api.getOperation.mockResolvedValue({ ...PAYMENT_OPERATION, kind: 'reverse_operation', effect: REVERSAL_PROPOSAL.effect, summary_pt_br: 'Pagamento parcial desfeito.' });
    mount('/ai?run=run-0003');
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Compensação (desfazer)' }));
    expect(applied.getByText('Gravada')).toBeInTheDocument();
    expect(applied.getByText('Desfeito')).toBeInTheDocument();
    expect(applied.queryByRole('button', { name: 'Desfazer' })).not.toBeInTheDocument();
  });

  it('escrita desligada no servidor: Desfazer fica desabilitado e a tela explica', async () => {
    api.getStatus.mockResolvedValue({ ...STATUS_SINGLE_SPACE, flags: { cloud: false, email: true, write: false } });
    mount('/ai?run=run-0003');
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    const undo = applied.getByRole('button', { name: 'Desfazer' });
    expect(undo).toBeDisabled();
    expect(applied.getByText(/não é possível desfazer por aqui agora/)).toBeInTheDocument();
    fireEvent.click(undo);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(api.reverseOperation).not.toHaveBeenCalled();
  });

  it('operação gravada usa rótulos no passado ("Estado gravado", "Gravado")', async () => {
    mount('/ai?run=run-0003');
    const applied = within(await screen.findByRole('article', { name: 'Operação gravada: Baixa em conta a pagar' }));
    expect(applied.getByText('Estado gravado:')).toBeInTheDocument();
    expect(applied.queryByText('Estado depois de aplicar:')).not.toBeInTheDocument();
  });
});

describe('troca de espaço financeiro', () => {
  beforeEach(() => { api.getStatus.mockResolvedValue(STATUS_READY); });

  it('fecha a execução e a proposta abertas: nada do espaço anterior fica aprovável sob o novo', async () => {
    api.getRun.mockResolvedValue(WAITING_PAYMENT);
    mount('/ai?run=run-0001');
    await proposalCard('Baixa em conta a pagar');
    expect(screen.getByRole('region', { name: 'Andamento' })).toBeInTheDocument();

    await userEvent.selectOptions(spaceSelect(), BUSINESS_SPACE.id);
    await waitFor(() => expect(api.listRuns).toHaveBeenCalledWith({ financial_space_id: BUSINESS_SPACE.id, limit: 5 }, expect.anything()));
    await within(screen.getByRole('region', { name: 'Execuções recentes' })).findByText(/Nenhuma execução ainda/);

    expect(screen.queryByRole('region', { name: 'Andamento' })).not.toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprovar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Três estados que não são a mesma coisa' })).not.toBeInTheDocument();
    expect(screen.queryByText('Casa')).not.toBeInTheDocument();
  });

  it('resposta de um envio que chega depois da troca não abre a execução do espaço anterior', async () => {
    const pending = deferred<RunAccepted>();
    api.createRun.mockImplementation(() => pending.promise);
    mount();
    fireEvent.change(await messageField(), { target: { value: 'Quanto falta pagar em outubro?' } });
    await userEvent.click(sendButton());
    expect(api.createRun).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ financial_space_id: PERSONAL_SPACE.id }), expect.anything());

    await userEvent.selectOptions(spaceSelect(), BUSINESS_SPACE.id);
    await act(async () => pending.resolve(ACCEPTED));

    expect(await screen.findByText('O pedido foi aceito no espaço "Casa". Volte a esse espaço para acompanhar a execução.')).toBeInTheDocument();
    expect(spaceSelect()).toHaveValue(BUSINESS_SPACE.id);
    expect(screen.queryByRole('region', { name: 'Andamento' })).not.toBeInTheDocument();
    expect(api.getRun).not.toHaveBeenCalled();
    expect(await messageField()).toHaveValue('');
  });

  it('retoma a execução pendente do espaço para o qual o titular trocou', async () => {
    api.listRuns.mockImplementation(async query => (query?.financial_space_id === BUSINESS_SPACE.id
      ? { runs: [{ run_id: 'run-0009', status: 'waiting_review', task: 'statement_import', created_at: '2026-10-01T12:00:00Z' }], next_cursor: null }
      : { runs: [], next_cursor: null }));
    api.getRun.mockResolvedValue(makeRun({ run_id: 'run-0009', task: 'statement_import', status: 'waiting_review', scope: { financial_space: BUSINESS_SPACE, accounts: [] }, progress: { stage: 'waiting_review', steps: [] } }));
    mount();
    await within(await screen.findByRole('region', { name: 'Execuções recentes' })).findByText(/Nenhuma execução ainda/);
    expect(api.getRun).not.toHaveBeenCalled();

    await userEvent.selectOptions(spaceSelect(), BUSINESS_SPACE.id);
    await screen.findByText('Aguardando a sua revisão.');
    expect(api.getRun).toHaveBeenCalledWith('run-0009', expect.anything());
    expect(runPanel().getByText('Marketing digital')).toBeInTheDocument();
  });
});

describe('sessão perdida durante o acompanhamento', () => {
  it('401 ao consultar a execução leva ao estado explicado, sem redirecionar', async () => {
    api.getStatus.mockResolvedValueOnce(STATUS_SINGLE_SPACE).mockRejectedValue(UNAUTHORIZED());
    api.getRun.mockRejectedValue(UNAUTHORIZED());
    mount('/ai?run=run-0001');
    expect(await screen.findByRole('heading', { name: 'Falta iniciar a sessão do operador' })).toBeInTheDocument();
    expect(api.getStatus).toHaveBeenCalledTimes(2);
    expect(screen.queryByLabelText('Seu pedido')).not.toBeInTheDocument();
    expect(screen.queryByText('TELA DE LOGIN')).not.toBeInTheDocument();
    expect(screen.queryByText('OUTRA TELA')).not.toBeInTheDocument();
  });
});
