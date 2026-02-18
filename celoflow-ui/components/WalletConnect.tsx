import React, { useState, useEffect } from 'react';
import { useAccount, useConnect, useDisconnect, useBalance, useReadContract } from 'wagmi';
import { Wallet, ChevronDown, LogOut, Copy, Check, X } from 'lucide-react';
import { useI18n } from '../lib/language';
import { useTokenBalances } from '../hooks/useTokenBalances';
import { TokenPortfolio } from './TokenPortfolio';
import { tokenBalanceService } from '../services/tokenBalanceService';
import { AuthStatus } from './AuthStatus';
import { parseAbi } from 'viem';
import { TokenBalance } from '../types';
import { TOKEN_REGISTRY } from '../lib/token-registry';

function truncateAddress(address: string): string {
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

function formatBalance(value: bigint | undefined, decimals: number = 18): string {
  if (value === undefined) return '0.00';
  const divisor = BigInt(10 ** decimals);
  const whole = value / divisor;
  const frac = value % divisor;
  const fracStr = frac.toString().padStart(decimals, '0').slice(0, 4);
  return `${whole}.${fracStr}`;
}

// Token icon colors matching TokenPortfolio
const getTokenIcon = (symbol: string) => {
  const iconColors: Record<string, string> = {
    'CELO': 'bg-green-500',
    'USDm': 'bg-blue-500',
    'USDC': 'bg-blue-600',
    'USDT': 'bg-green-600',
    'EURm': 'bg-yellow-500',
    'BRLm': 'bg-emerald-500',
    'XOFm': 'bg-orange-500',
    'KESm': 'bg-red-500',
    'PHPm': 'bg-indigo-500',
    'COPm': 'bg-amber-500',
    'GBPm': 'bg-purple-500',
    'CADm': 'bg-rose-500',
    'AUDm': 'bg-cyan-500',
    'ZARm': 'bg-teal-500',
    'GHSm': 'bg-lime-600',
    'NGNm': 'bg-fuchsia-500',
    'JPYm': 'bg-pink-500',
    'CHFm': 'bg-sky-500',
    'default': 'bg-gray-500'
  };
  
  return iconColors[symbol] || iconColors.default;
};

// Token metadata for display
const getTokenMetadata = (symbol: string) => {
  const metadata: Record<string, { name: string; category: 'mento' | 'tether' | 'circle' | 'vnx' | 'mountain' | 'angle' | 'glo' | 'brla' | 'minteo' | 'gooddollar' | 'native'; decimals: number }> = {
    'USDT': { name: 'Tether USD', category: 'tether', decimals: 6 },
    'USDm': { name: 'Mento Dollar', category: 'mento', decimals: 18 },
    'EURm': { name: 'Mento Euro', category: 'mento', decimals: 18 },
    'BRLm': { name: 'Mento Brazilian Real', category: 'mento', decimals: 18 },
    'CELO': { name: 'Celo', category: 'native', decimals: 18 }
  };
  
  return metadata[symbol] || { name: symbol, category: 'mento', decimals: 18 };
};

// Mock USD prices for tokens (would be fetched from price API in production)
const MOCK_PRICE_DATA: Record<string, number> = {
  'CELO': 0.85,
  'USDm': 1.00,
  'EURm': 1.08,
  'BRLm': 0.20,
  'USDC': 1.00,
  'USDT': 1.00,
  'XOFm': 0.0016,
  'KESm': 0.0081,
  'PHPm': 0.018,
  'COPm': 0.00027,
  'GBPm': 1.27,
  'CADm': 0.74,
  'AUDm': 0.66,
  'ZARm': 0.053,
  'GHSm': 0.083,
  'NGNm': 0.00067,
  'JPYm': 0.0067,
  'CHFm': 1.12,
  'vEUR': 1.08,
  'vGBP': 1.27,
  'vCHF': 1.12,
  'USDM': 1.00,
  'USDA': 1.00,
  'EURA': 1.08,
  'USDGLO': 1.00,
  'BRLA': 0.20,
  'COPM': 0.00027,
  'G$': 1.00
};

export const WalletConnect: React.FC = () => {
  const { address, isConnected, chain } = useAccount();
  const { connectors, connect, isPending } = useConnect();
  const { disconnect } = useDisconnect();
  
  // Use custom chain ID from environment variables if available
  const customChainId = import.meta.env.VITE_CELO_CHAIN_ID
  const balanceChainId = chain?.id || (customChainId ? parseInt(customChainId) : 42220)
  
  const { data: nativeBalanceData } = useBalance({ 
    address,
    chainId: balanceChainId
  });
  const { t } = useI18n();

  // Simple ERC-20 token balances using useReadContract
  const erc20Abi = parseAbi([
    'function balanceOf(address account) view returns (uint256)',
    'function decimals() view returns (uint8)',
    'function symbol() view returns (string)'
  ]);

  // Get tokens available on current network (filter out native CELO and tokens not deployed on Sepolia)
  const availableTokens = Object.values(TOKEN_REGISTRY).filter(
    token => token.contractAddress.sepolia !== '0x0000000000000000000000000000000000000000' && 
             token.symbol !== 'CELO'
  );

  // Dynamic token balance queries
  const tokenBalanceQueries = availableTokens.map(token => {
    const { data: balance } = useReadContract({
      address: token.contractAddress.sepolia as `0x${string}`,
      abi: erc20Abi,
      functionName: 'balanceOf',
      args: [address as `0x${string}`],
      chainId: balanceChainId,
      query: { enabled: isConnected && !!address }
    });
    
    return { token, balance };
  });

  // Temporarily disable multi-token balance hook to restore working UI
  // const { 
  //   portfolio, 
  //   summary, 
  //   refreshState, 
  //   refreshBalances, 
  //   toggleAutoRefresh, 
  //   isLoading, 
  //   error 
  // } = useTokenBalances({ 
  //   includeZeroBalances: true, // Show all tokens for debugging
  //   priorityTokensOnly: false,
  //   autoRefresh: true
  // });

  const [showOptions, setShowOptions] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-wallet-widget]')) {
        setShowOptions(false);
        setShowProfile(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const handleCopy = async () => {
    if (!address) return;
    await navigator.clipboard.writeText(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyTokenAddress = async (address: string, symbol: string) => {
    await navigator.clipboard.writeText(address);
    setCopiedToken(symbol);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  // Convert balance data to TokenBalance format for consistent display
  const createTokenBalance = (symbol: string, balance: bigint | undefined, contractAddress: string): TokenBalance | null => {
    if (!balance || balance === 0n) return null;
    
    const metadata = getTokenMetadata(symbol);
    const formattedBalance = formatBalance(balance, metadata.decimals);
    
    return {
      symbol,
      name: metadata.name,
      contractAddress,
      balance,
      decimals: metadata.decimals,
      formattedBalance,
      category: metadata.category,
      usdValue: undefined, // Could be calculated later
      change24h: undefined,
      isNative: symbol === 'CELO',
      lastUpdated: new Date()
    };
  };

  // Create token balance array dynamically
  const tokenBalances: TokenBalance[] = tokenBalanceQueries
    .map(({ token, balance }) => {
      if (!balance || balance === 0n) return null;
      
      const formattedBalance = formatBalance(balance, token.decimals);
      
      return {
        symbol: token.symbol,
        name: token.name,
        contractAddress: token.contractAddress.sepolia,
        balance,
        decimals: token.decimals,
        formattedBalance,
        category: token.category,
        usdValue: undefined, // Could be calculated later
        change24h: undefined,
        isNative: false,
        lastUpdated: new Date(),
        error: undefined
      } as TokenBalance;
    })
    .filter((token): token is TokenBalance => token !== null);

  if (isConnected && address) {
    return (
      <div className="relative" data-wallet-widget>
        <button
          onClick={() => setShowProfile(!showProfile)}
          className="flex items-center gap-2 px-3 py-2 rounded-full bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-celo-green transition-colors text-sm font-medium"
        >
          <div className="w-6 h-6 rounded-full bg-linear-to-tr from-celo-green to-blue-500 shrink-0" />
          <span className="text-gray-900 dark:text-white hidden sm:inline">
            {truncateAddress(address)}
          </span>
          {nativeBalanceData && (
            <span className="text-gray-500 dark:text-gray-400 text-xs hidden md:inline">
              {formatBalance(nativeBalanceData.value, nativeBalanceData.decimals)} {nativeBalanceData.symbol}
            </span>
          )}
          <ChevronDown className={`w-3 h-3 text-gray-400 transition-transform ${showProfile ? 'rotate-180' : ''}`} />
        </button>

        {showProfile && (
          <div className="absolute right-0 top-full mt-2 w-64 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden z-50 animate-fade-in-up">
            <div className="p-4 border-b border-gray-100 dark:border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold">
                  {t('Connected')}
                </span>
                <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                  {chain?.name || (chain?.id === 42220 ? 'Celo Mainnet' : chain?.id === 11142220 ? 'Celo Sepolia' : t('Unknown'))}
                </span><br/>
                <AuthStatus walletAddress={address} />
              </div>
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm text-gray-900 dark:text-white">
                  {truncateAddress(address)}
                </span>
                <button
                  onClick={handleCopy}
                  className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                  title={t('Copy address')}
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <Copy className="w-3.5 h-3.5 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {/* Simple CELO Balance Display - Working Version */}
            {nativeBalanceData && (
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('Native Balance')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-white">
                  {formatBalance(nativeBalanceData.value, nativeBalanceData.decimals)}{' '}
                  <span className="text-sm text-gray-500 dark:text-gray-400 font-normal">
                    {nativeBalanceData.symbol}
                  </span>
                </div>
                <div className="text-xs text-green-600 dark:text-green-400 mt-1">
                  ≈ ${(parseFloat(formatBalance(nativeBalanceData.value, nativeBalanceData.decimals)) * 0.85).toFixed(2)} USD
                </div>
              </div>
            )}

            {/* Enhanced Multi-Token Display */}
            {tokenBalances.length > 0 && (
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-3 flex items-center justify-between">
                  <span>{t('Token Balances')}</span>
                  <span className="text-celo-green">{tokenBalances.length} tokens</span>
                </div>
                
                <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 scrollbar-track-transparent">
                  {tokenBalances.map(token => (
                    <div
                      key={token.symbol}
                      className="flex items-center justify-between py-2 hover:bg-gray-50 dark:hover:bg-gray-700/30 rounded-lg px-2 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-6 h-6 rounded-full ${getTokenIcon(token.symbol)} flex items-center justify-center shrink-0`}>
                          <span className="text-white text-xs font-bold">
                            {token.symbol?.slice(0, 2) || '??'}
                          </span>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {token.symbol || 'Unknown'}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            {token.category || 'Token'}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-bold text-gray-900 dark:text-white">
                          {token.formattedBalance || formatBalance(token.balance, token.decimals)}
                        </div>
                        <div className="text-xs text-green-600 dark:text-green-400">
                          {(() => {
                            const price = MOCK_PRICE_DATA[token.symbol];
                            if (!price) return '';
                            return `≈ ${(parseFloat(formatBalance(token.balance, token.decimals)) * price).toFixed(2)} USD`;
                          })()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Token Actions Footer */}
                <div className="mt-3 pt-2 border-t border-gray-100 dark:border-gray-700">
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {t('Live balances from Celo network')}
                    </div>
                    <button
                      onClick={() => window.open('https://celoscan.io/', '_blank')}
                      className="text-xs text-celo-green hover:text-green-600 flex items-center gap-1"
                    >
                      {t('View on CeloScan')}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TODO: Add more tokens gradually once basic UI is stable */}
            {/* <TokenPortfolio
              portfolio={portfolio}
              summary={summary}
              refreshState={refreshState}
              onRefresh={refreshBalances}
              onToggleAutoRefresh={toggleAutoRefresh}
              compact={false}
            /> */}

            <button
              onClick={() => {
                disconnect();
                setShowProfile(false);
              }}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/10 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              {t('Disconnect Wallet')}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="relative" data-wallet-widget>
      <button
        onClick={() => setShowOptions(!showOptions)}
        disabled={isPending}
        className="flex items-center gap-2 px-4 py-2 bg-celo-green text-white rounded-full text-sm font-medium hover:bg-green-500 transition-colors disabled:opacity-50 shadow-lg shadow-green-500/20"
      >
        <Wallet className="w-4 h-4" />
        {isPending ? t('Connecting…') : t('Connect Wallet')}
      </button>

      {showOptions && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden z-50 animate-fade-in-up">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              {t('Connect a Wallet')}
            </span>
            <button
              onClick={() => setShowOptions(false)}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>
          <div className="p-2 space-y-1">
            {connectors.map((connector) => {
              const handleClick = () => {
                connect({ connector });
                setShowOptions(false);
              };
              return (
                <WalletOption
                  key={connector.uid}
                  name={connector.name}
                  onClick={handleClick}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

function WalletOption({ name, onClick }: { name: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left"
    >
      <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center shrink-0">
        <Wallet className="w-4 h-4 text-gray-600 dark:text-gray-300" />
      </div>
      <span className="text-sm font-medium text-gray-900 dark:text-white">{name}</span>
    </button>
  );
}
