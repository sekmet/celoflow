export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  type?: 'text' | 'transaction_preview' | 'transaction_success';
  transactionData?: TransactionIntent;
}

export interface TransactionIntent {
  amount: number;
  currency: string;
  recipient: string;
  recipientCurrency: string;
  convertedAmount: number;
  fees: number;
  feeBreakdown?: {
    mentoFee: number;
    networkFee: number;
    securityFee: number;
  };
  savings: number;
  route: string[];
  frequency?: string;
  exchangeRate?: number;
  isRealTimeRate?: boolean;
  startDate?: string;
}

export interface TransactionHistoryItem {
  id: string;
  date: string;
  intent: TransactionIntent;
  status: 'completed' | 'scheduled' | 'processing' | 'failed' | 'cancelled';
}

export interface ExchangeRate {
  pair: string;
  rate: number;
}

export interface Contact {
  id: string;
  name: string;
  address: string;
  network: string;
  city: string;
  country: string;
  avatar: string;
  phone: string;
  email: string;
  notes: string;
  favorite: boolean;
  blocked: boolean;
  group: string;
  createdAt: string;
  updatedAt: string;
}