import React, { useState, useEffect } from 'react';
import { useAccount, useConnect, useDisconnect, useBalance } from 'wagmi';
import { Wallet, ChevronDown, LogOut, Copy, Check, X } from 'lucide-react';
import { useI18n } from '../lib/language';

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
  const { data: balanceData } = useBalance({ address });
  const { t } = useI18n();

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
          {balanceData && (
            <span className="text-gray-500 dark:text-gray-400 text-xs hidden md:inline">
              {formatBalance(balanceData.value, balanceData.decimals)} {balanceData.symbol}
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
                  {chain?.name || t('Unknown')}
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

            {balanceData && (
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">{t('Balance')}</div>
                <div className="text-lg font-bold text-gray-900 dark:text-white">
                  {formatBalance(balanceData.value, balanceData.decimals)}{' '}
                  <span className="text-sm text-gray-500 dark:text-gray-400 font-normal">
                    {balanceData.symbol}
                  </span>
                </div>
              </div>
            )}

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
