export type TransactionType = 'income' | 'expense' | 'transfer';
export type TransactionStatus = 'paid' | 'pending' | 'overdue' | 'cancelled';
export type TransactionEntrySource = 'manual' | 'csv' | 'ofx';

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
  entry_source?: TransactionEntrySource;
  fitid?: string | null;
  import_batch_id?: string | null;
}

export interface ImportBatchRecord {
  id: string;
  filename: string;
  file_format: string;
  account_id?: string;
  total_parsed: number;
  imported_count: number;
  ignored_count: number;
  duplicate_count: number;
  unclassified_count: number;
  total_income: number;
  total_expense: number;
  total_transfer: number;
  ledger_balance?: number | null;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'rolled_back';
  metadata?: Record<string, any>;
  created_at: string;
  rolled_back_at?: string | null;
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


