export interface Transaction {
  id: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  category_id: string;
  date: string;
  status?: 'paid' | 'pending' | 'overdue' | 'cancelled';
  responsible_person?: string;
  account_id?: string;
  category?: {
    id: string;
    name: string;
    color: string;
    icon: string;
  };
}

export interface Account {
  id: string;
  name: string;
  type: 'wallet' | 'checking' | 'savings' | 'credit_card' | 'investment';
  current_balance: number;
  initial_balance: number;
  institution?: string;
  color: string;
  icon?: string;
  is_active: boolean;
}

export interface DashboardData {
  total_balance: number;
  total_income: number;
  total_expense: number;
  pending_transactions: number;
  recent_transactions: Transaction[];
}
