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
  // User wallet signing result fields
  txHash?: string;
  explorerUrl?: string;
  signerType?: 'tee' | 'user';
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

export interface ProviderComparison {
  name: string;
  total_fee: number;
  fee_percentage: number;
  speed: string;
}

export interface TransferFees {
  network_fee: number;
  network_fee_currency: string;
  service_fee: number;
  service_fee_currency: string;
  service_fee_pct: number;
  service_fee_tier: string;
  total_fee_usd: number;
  total_fee_pct: number;
}

export interface TransferRoute {
  available: boolean;
  from_currency?: string;
  to_currency?: string;
  amount?: number;
  estimated_output?: number;
  rate?: number;
  route_type?: string;
  slippage_pct?: number;
  reason?: string;
}

export interface TEEBalance {
  sufficient: boolean;
  auto_swap_needed: boolean;
  tee_address?: string;
  token?: string;
  balance?: number;
  required?: number;
  deficit?: number;
}

export interface SavingsInfo {
  available: boolean;
  celoflow_fee: number;
  celoflow_fee_pct: number;
  cheapest_provider?: string;
  cheapest_provider_fee?: number;
  savings_vs_cheapest?: number;
  savings_vs_cheapest_pct?: number;
  most_expensive_provider?: string;
  savings_vs_most_expensive?: number;
}

export interface TransferPreview {
  preview_id: string;
  recipient: string;
  amount: number;
  token: string;
  destination_country: string;
  route: TransferRoute;
  fees: TransferFees;
  comparisons: ProviderComparison[];
  savings: SavingsInfo;
  tee_balance: TEEBalance;
  created_at: number;
  expires_at: number;
  expires_in_seconds: number;
  error?: string;
}