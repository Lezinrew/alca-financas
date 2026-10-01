import type { ComponentType, ReactNode } from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { STATUS_SINGLE_SPACE } from './fixtures';

// O menu real (AppShell) e as rotas reais (App) com a flag de build em cada valor.
// Dublês só do que está fora deste componente: autenticação, widget de chat e a
// fronteira HTTP da IA. `vi.hoisted` mantém o mesmo espião entre as recargas de módulo.
const ai = vi.hoisted(() => ({ getStatus: vi.fn(), listRuns: vi.fn() }));
vi.mock('../../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => children,
  useAuth: () => ({ user: { name: 'Pessoa de Teste', email: 'pessoa@exemplo.test' }, logout: vi.fn(), isAuthenticated: true, loading: false }),
}));
vi.mock('../chat/ChatWidget', () => ({ ChatWidget: () => null }));
// As telas de login (importadas pelo App, mas não exibidas aqui) criam um cliente Supabase
// na carga do módulo; o dublê evita um cliente novo a cada recarga.
vi.mock('../../utils/supabaseClient', () => ({
  supabase: { auth: { getSession: vi.fn(async () => ({ data: { session: null } })), onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })) } },
}));
vi.mock('./aiApi', () => ({ aiApi: { getStatus: ai.getStatus, listRuns: ai.listRuns } }));

// Cada caso recarrega o aplicativo inteiro; a folga evita falso negativo em máquina ocupada.
vi.setConfig({ testTimeout: 60_000 });

const stubFlag = (value: string | undefined) => {
  vi.resetModules();
  if (value === undefined) vi.stubEnv('VITE_ENABLE_AI_OPERATOR', undefined as unknown as string);
  else vi.stubEnv('VITE_ENABLE_AI_OPERATOR', value);
};

/** A flag é lida na carga do módulo; por isso o módulo é recarregado a cada valor. */
const loadWithFlag = async (value: string | undefined) => {
  stubFlag(value);
  const flag = await import('./featureFlag');
  const shell = await import('../layout/AppShell');
  return { enabled: flag.AI_OPERATOR_ENABLED, AppShell: shell.default };
};

const renderShell = (AppShell: ComponentType) => render(
  <MemoryRouter initialEntries={['/dashboard']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    <Routes><Route element={<AppShell />}><Route path="*" element={<p>conteúdo</p>} /></Route></Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  ai.getStatus.mockResolvedValue(STATUS_SINGLE_SPACE);
  ai.listRuns.mockResolvedValue({ runs: [], next_cursor: null });
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); window.history.pushState({}, '', '/'); });

const OFF_VALUES = [undefined, '', 'false', '1', 'yes', 'TRUE', ' true'];

describe('flag VITE_ENABLE_AI_OPERATOR: item de menu', () => {
  it.each(OFF_VALUES)('valor %j mantém o operador fora do menu', async value => {
    const { enabled, AppShell } = await loadWithFlag(value);
    expect(enabled).toBe(false);
    renderShell(AppShell);
    // O resto do aplicativo continua no menu; só o operador não aparece.
    expect(screen.getByRole('link', { name: 'Contas a pagar' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Importar' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Operador' })).not.toBeInTheDocument();
  });

  it('somente "true" mostra o item Operador apontando para /ai', async () => {
    const { enabled, AppShell } = await loadWithFlag('true');
    expect(enabled).toBe(true);
    renderShell(AppShell);
    expect(screen.getByRole('link', { name: 'Operador' })).toHaveAttribute('href', '/ai');
    expect(screen.getByRole('link', { name: 'Contas a pagar' })).toBeInTheDocument();
  });
});

/**
 * O item de menu sumir não basta: quem digitar /ai (ou tiver o link salvo) não pode
 * chegar à tela enquanto a função está desligada. Aqui o `App` real é carregado com
 * as rotas reais, na URL /ai, para cada valor da flag.
 */
describe('flag VITE_ENABLE_AI_OPERATOR: rota /ai', () => {
  const openAppAt = async (path: string, value: string | undefined) => {
    stubFlag(value);
    window.history.pushState({}, '', path);
    const { default: App } = await import('../../App');
    // A página é carregada antes, para o `lazy` da rota (se ela existir) resolver logo:
    // assim "a tela não apareceu" significa "a rota não existe", e não "ainda carregando".
    await import('./AiOperatorPage');
    render(<App />);
    await screen.findByRole('link', { name: 'Contas a pagar' });
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 50)); });
  };

  it.each(OFF_VALUES)('valor %j: /ai não abre a tela do operador e não chama a API de IA', async value => {
    await openAppAt('/ai', value);
    expect(screen.queryByText('Peça, confira e aprove')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Seu pedido')).not.toBeInTheDocument();
    expect(ai.getStatus).not.toHaveBeenCalled();
    // O aplicativo continua de pé: o menu está lá, sem o item do operador.
    expect(screen.getByRole('link', { name: 'Importar' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Operador' })).not.toBeInTheDocument();
  });

  it('somente "true": /ai abre a tela do operador dentro do aplicativo', async () => {
    await openAppAt('/ai', 'true');
    expect(await screen.findByText('Peça, confira e aprove')).toBeInTheDocument();
    expect(await screen.findByLabelText('Seu pedido')).toBeInTheDocument();
    expect(ai.getStatus).toHaveBeenCalled();
    expect(screen.getByRole('link', { name: 'Operador' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('heading', { level: 1, name: 'Operador' })).toBeInTheDocument();
  });
});
