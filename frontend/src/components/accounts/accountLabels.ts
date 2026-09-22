import type { Account } from '../../types/account';

export const accountTypeNames: Record<Account['type'], string> = {
  wallet: 'Carteira', checking: 'Conta Corrente', savings: 'Poupança', credit_card: 'Cartão de Crédito', investment: 'Investimento',
};

export const getAccountTypeName = (type: Account['type']) => accountTypeNames[type] ?? 'Conta';

export const ACCOUNT_SAVE_ERROR = 'Não foi possível salvar a conta. Suas alterações foram mantidas. Tente novamente.';
export const ACCOUNT_DELETE_ERROR = 'Não foi possível excluir a conta. Contas com transações vinculadas não podem ser excluídas.';
