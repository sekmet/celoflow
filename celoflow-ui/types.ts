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

// Multi-token wallet balance interfaces
export interface TokenBalance {
  symbol: string;
  name: string;
  balance: bigint;
  decimals: number;
  formattedBalance: string;
  usdValue?: number;
  change24h?: number;
  contractAddress: string;
  category: 'mento' | 'tether' | 'circle' | 'vnx' | 'mountain' | 'angle' | 'glo' | 'brla' | 'minteo' | 'gooddollar' | 'native';
  isNative: boolean;
  lastUpdated: Date;
  error?: string;
}

export interface TokenInfo {
  symbol: string;
  name: string;
  decimals: number;
  contractAddress: {
    mainnet: string;
    sepolia: string;
  };
  category: 'mento' | 'tether' | 'circle' | 'vnx' | 'mountain' | 'angle' | 'glo' | 'brla' | 'minteo' | 'gooddollar' | 'native';
  logoUrl?: string;
  coingeckoId?: string;
  description?: string;
}

export interface TokenPortfolio {
  address: string;
  chainId: number;
  tokens: TokenBalance[];
  totalValueUsd: number;
  totalValueChange24h: number;
  lastUpdated: Date;
  isLoading: boolean;
  error?: string;
}

export interface PortfolioSummary {
  totalValueUsd: number;
  totalValueChange24h: number;
  totalValueChangePercent24h: number;
  tokenCount: number;
  hasZeroBalanceTokens: boolean;
  networkName: string;
}

export interface BalanceRefreshState {
  isRefreshing: boolean;
  lastRefreshTime: Date;
  refreshError?: string;
  autoRefreshEnabled: boolean;
}