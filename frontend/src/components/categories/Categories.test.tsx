import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Categories from './Categories';
import { categoriesAPI } from '../../utils/api';
import type { Category } from './types';

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ isAuthenticated: true, loading: false }) }));
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../utils/api', () => ({
  categoriesAPI: { getAll: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));

const food: Category = { id: 'cat-1', name: 'Alimentação', type: 'expense', color: '#FF6B6B', icon: 'basket', description: 'Comida' };
const salary: Category = { id: 'cat-2', name: 'Salário', type: 'income', color: '#10b981', icon: 'currency-dollar' };
const response = <T,>(data: T) => ({ data }) as never;
const deferred = <T,>() => {
  let resolve!: (data: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
const mount = () => render(<Categories />);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(categoriesAPI.getAll).mockResolvedValue(response([food, salary]));
  vi.mocked(categoriesAPI.delete).mockResolvedValue(response({}));
  vi.mocked(categoriesAPI.create).mockResolvedValue(response(food));
});
afterEach(cleanup);

describe('Categories', () => {
  it('falha de rede mostra indisponibilidade sem estado vazio falso nem contagem zero', async () => {
    vi.mocked(categoriesAPI.getAll).mockRejectedValueOnce(new Error('Network Error'));
    mount();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Indisponível.');
    expect(screen.queryByText('Network Error')).not.toBeInTheDocument();
    expect(screen.queryByText(/Nenhuma categoria/)).not.toBeInTheDocument();
    expect(screen.queryByText('0 categorias')).not.toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(2);
    await userEvent.click(within(alert).getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByText(food.name)).toBeInTheDocument();
    expect(categoriesAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('separa receitas e despesas e mostra estado vazio apenas com dados carregados', async () => {
    vi.mocked(categoriesAPI.getAll).mockResolvedValueOnce(response([food]));
    mount();
    const income = within(await screen.findByRole('region', { name: 'Receitas' }));
    const expense = within(screen.getByRole('region', { name: 'Despesas' }));
    expect(income.getByText('Nenhuma categoria de receita cadastrada')).toBeInTheDocument();
    expect(income.getByText('0 categorias')).toBeInTheDocument();
    expect(expense.getByText(food.name)).toBeInTheDocument();
    expect(expense.getByText('1 categorias')).toBeInTheDocument();
  });

  it('exclusão só chama a API após confirmar no diálogo que nomeia a categoria', async () => {
    mount();
    await screen.findByText(food.name);
    await userEvent.click(screen.getByRole('button', { name: `Mais ações para ${food.name}` }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Excluir' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Excluir categoria' }));
    expect(dialog.getByText(food.name)).toBeInTheDocument();
    expect(dialog.getByText('Despesa')).toBeInTheDocument();
    expect(categoriesAPI.delete).not.toHaveBeenCalled();
    await userEvent.click(dialog.getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(categoriesAPI.delete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: `Mais ações para ${food.name}` }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Excluir' }));
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirmar exclusão' }));
    await waitFor(() => expect(categoriesAPI.delete).toHaveBeenCalledExactlyOnceWith(food.id));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(categoriesAPI.getAll).toHaveBeenCalledTimes(2);
  });

  it('exclusão recusada mantém o diálogo com mensagem fixa', async () => {
    vi.mocked(categoriesAPI.delete).mockRejectedValueOnce(new Error('Network Error'));
    mount();
    await screen.findByText(salary.name);
    await userEvent.click(screen.getByRole('button', { name: `Mais ações para ${salary.name}` }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Excluir' }));
    const dialog = within(screen.getByRole('dialog'));
    await userEvent.click(dialog.getByRole('button', { name: 'Confirmar exclusão' }));
    expect(await dialog.findByRole('alert')).toHaveTextContent('Não foi possível excluir a categoria.');
    expect(screen.queryByText('Network Error')).not.toBeInTheDocument();
  });

  it('formulário foca o nome e bloqueia duplo envio', async () => {
    mount();
    await screen.findByText(food.name);
    await userEvent.click(screen.getByRole('button', { name: 'Nova categoria' }));
    const dialog = within(screen.getByRole('dialog', { name: 'categories.add' }));
    const name = dialog.getByLabelText('categories.name *');
    expect(name).toHaveFocus();
    await userEvent.type(name, 'Pets');
    const pending = deferred<ReturnType<typeof response>>();
    vi.mocked(categoriesAPI.create).mockImplementationOnce(() => pending.promise);
    const save = dialog.getByRole('button', { name: 'common.save' });
    fireEvent.click(save); fireEvent.click(save);
    expect(categoriesAPI.create).toHaveBeenCalledTimes(1);
    expect(categoriesAPI.create).toHaveBeenCalledWith(expect.objectContaining({ name: 'Pets', type: 'expense' }));
    expect(dialog.getByRole('button', { name: 'Salvando…' })).toBeDisabled();
    await act(async () => pending.resolve(response(food)));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});
