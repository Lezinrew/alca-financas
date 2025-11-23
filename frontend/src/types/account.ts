export type AccountType = 'wallet' | 'checking' | 'savings' | 'credit_card' | 'investment';

export interface Account {
  id?: string;
  name: string;
  type: AccountType;
  current_balance?: number;
  projected_balance?: number;
  initial_balance?: number;
  institution?: string;
  color?: string;
  icon?: string;
  is_active: boolean;
  limit?: number; // Limite total do cartão de crédito (opcional)
}

export type AccountPayload = Omit<Account, 'id'>;

