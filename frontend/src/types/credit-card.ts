export interface CreditCard {
  id: string;
  name: string;
  limit: number;
  closingDay: number;
  dueDay: number;
  color: string;
  icon?: string;
  is_active?: boolean;
  used?: number;
  available?: number; // Limite disponível (pode ser negativo)
  account_id?: string;
  card_type?: string;
}

export type CreditCardPayload = Omit<CreditCard, 'id' | 'used'> & {
  account_id: string;
  card_type: string;
  is_active: boolean;
};

