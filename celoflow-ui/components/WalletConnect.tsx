import React, { useState, useEffect } from 'react';
import { useAccount, useConnect, useDisconnect, useBalance, useReadContract } from 'wagmi';
import { Wallet, ChevronDown, LogOut, Copy, Check, X } from 'lucide-react';
import { useI18n } from '../lib/language';
import { useTokenBalances } from '../hooks/useTokenBalances';
import { TokenPortfolio } from './TokenPortfolio';
import { tokenBalanceService } from '../services/tokenBalanceService';
import { parseAbi } from 'viem';

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

  // USDC balance (Note: No Sepolia address listed in docs, skipping for now)
  // const { data: usdcBalance } = useReadContract({
  //   address: '0xceba9300f2b948710d2653dd7b07f33a8b32118c' as `0x${string}`,
  //   abi: erc20Abi,
  //   functionName: 'balanceOf',
  //   args: [address as `0x${string}`],
  //   chainId: balanceChainId,
  //   query: { enabled: isConnected && !!address }
  // });

  // USDT balance (Sepolia testnet address)
  const { data: usdtBalance } = useReadContract({
    address: '0xd077A400968890Eacc75cdc901F0356c943e4fDb' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  });

  // USDm balance (Sepolia testnet address)
  const { data: usdmBalance } = useReadContract({
    address: '0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  });

  // EURm balance (Sepolia testnet address)
  const { data: eurmbalance } = useReadContract({
    address: '0xA99dC247d6b7B2E3ab48a1fEE101b83cD6aCd82a' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  });

  // BRLm balance (Sepolia testnet address)
  const { data: brlmbalance } = useReadContract({
    address: '0x2294298942fdc79417DE9E0D740A4957E0e7783a' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
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

  if (isConnected && address) {
    return (
      <div className="relative" data-wallet-widget>
        <button
          onClick={() => setShowProfile(!showProfile)}
          className="flex items-center gap-2 px-3 py-2 rounded-full bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:border-celo-green transition-colors text-sm font-medium"
        >
          <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-celo-green to-blue-500 shrink-0" />
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
                  {chain?.name || (chain?.id === 42220 ? 'Celo Mainnet' : chain?.id === 44787 ? 'Celo Alfajores' : t('Unknown'))}
                </span>
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

            {/* Simple Multi-Token Display */}
            {(usdtBalance !== undefined || usdmBalance !== undefined || eurmbalance !== undefined || brlmbalance !== undefined) && (
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">{t('Token Balances')}</div>
                
                {/* USDT */}
                {usdtBalance !== undefined && (
                  <div className="flex justify-between items-center py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">USDT</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Tether USD</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-gray-900 dark:text-white">
                        {formatBalance(usdtBalance as bigint, 6)}
                      </div>
                      <div className="text-xs text-green-600 dark:text-green-400">
                        ≈ ${(parseFloat(formatBalance(usdtBalance as bigint, 6)) * 1.0).toFixed(2)}
                      </div>
                    </div>
                  </div>
                )}

                {/* USDm */}
                {usdmBalance !== undefined && (
                  <div className="flex justify-between items-center py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">USDm</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Mento Dollar</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-gray-900 dark:text-white">
                        {formatBalance(usdmBalance as bigint, 18)}
                      </div>
                      <div className="text-xs text-green-600 dark:text-green-400">
                        ≈ ${(parseFloat(formatBalance(usdmBalance as bigint, 18)) * 1.0).toFixed(2)}
                      </div>
                    </div>
                  </div>
                )}

                {/* EURm */}
                {eurmbalance !== undefined && (
                  <div className="flex justify-between items-center py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">EURm</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Mento Euro</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-gray-900 dark:text-white">
                        {formatBalance(eurmbalance as bigint, 18)}
                      </div>
                      <div className="text-xs text-green-600 dark:text-green-400">
                        ≈ ${(parseFloat(formatBalance(eurmbalance as bigint, 18)) * 1.08).toFixed(2)}
                      </div>
                    </div>
                  </div>
                )}

                {/* BRLm */}
                {brlmbalance !== undefined && (
                  <div className="flex justify-between items-center py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">BRLm</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Mento Brazilian Real</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-gray-900 dark:text-white">
                        {formatBalance(brlmbalance as bigint, 18)}
                      </div>
                      <div className="text-xs text-green-600 dark:text-green-400">
                        ≈ ${(parseFloat(formatBalance(brlmbalance as bigint, 18)) * 0.20).toFixed(2)}
                      </div>
                    </div>
                  </div>
                )}
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
