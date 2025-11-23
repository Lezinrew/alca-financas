export type TransactionType = 'income' | 'expense';
export type TransactionStatus = 'paid' | 'pending' | 'overdue' | 'cancelled';

export interface TransactionCategory {
  id: string;
  name: string;
  type: TransactionType;
  color?: string;
  icon?: string;
}

export interface InstallmentInfo {
  current: number;
  total: number;
}

export interface TransactionRecord {
  id: string;
  description: string;
  amount: number;
  type: TransactionType;
  category_id: string;
  category?: TransactionCategory;
  account_id?: string;
  date: string;
  status?: TransactionStatus;
  responsible_person?: string;
  is_recurring?: boolean;
  installment_info?: InstallmentInfo;
}

export interface TransactionSubmitPayload {
  description: string;
  amount: number;
  type: TransactionType;
  category_id: string;
  account_id?: string;
  date: string;
  is_recurring: boolean;
  installments: number;
  status: TransactionStatus;
  responsible_person: string;
}

