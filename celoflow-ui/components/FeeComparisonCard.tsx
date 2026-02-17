import React, { useState } from 'react';
import { TrendingUp, TrendingDown, Clock, Zap, ChevronDown, ChevronUp, RefreshCcw, Shield, AlertCircle, CheckCircle2, BarChart3, ArrowRight } from 'lucide-react';
import { useI18n } from '../lib/language';

interface ProviderComparison {
  provider: string;
  total_fee: number;
  fee_percentage: number;
  fx_markup: number;
  speed: string;
  recipient_receives: number;
  confidence: string;
  data_source: string;
  rank?: number;
  exchange_rate?: number;
  mid_market_rate?: number;
  fx_markup_pct?: number;
  breakdown?: {
    transfer_fee?: number;
    fx_markup_cost?: number;
    network_fee?: number;
    agent_fee?: number;
    liquidity_fee?: number;
  };
}

interface FeeComparisonData {
  amount: number;
  from_currency: string;
  destination_country: string;
  comparisons: ProviderComparison[];
  celoflow_rank: number;
  savings_vs_cheapest_traditional: number;
  savings_vs_most_expensive: number;
  recommendation: string;
  data_source: string;
  last_updated: number;
  provider_count: number;
}

interface FeeComparisonCardProps {
  data: FeeComparisonData;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

function getSpeedIcon(speed: string): React.ReactNode {
  if (speed.includes('second') || speed.includes('instant') || speed.includes('< 5')) {
    return <Zap className="w-3 h-3 text-green-500" />;
  }
  if (speed.includes('minute') || speed.includes('Minute')) {
    return <Clock className="w-3 h-3 text-yellow-500" />;
  }
  return <Clock className="w-3 h-3 text-gray-400" />;
}

function getConfidenceBadge(confidence: string, dataSource: string): React.ReactNode {
  if (confidence === 'high' || dataSource === 'realtime') {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        LIVE
      </span>
    );
  }
  if (confidence === 'simulated' || dataSource === 'simulated') {
    return (
      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
        SIM
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
      <AlertCircle className="w-2.5 h-2.5" />
      EST
    </span>
  );
}

function formatTimestamp(ts: number): string {
  if (!ts) return '';
  const date = new Date(ts * 1000);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return date.toLocaleDateString();
}

export const FeeComparisonCard: React.FC<FeeComparisonCardProps> = ({
  data,
  onRefresh,
  isRefreshing = false,
}) => {
  const { t } = useI18n();
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  const celoflow = data.comparisons.find(c => c.provider === 'CeloFlow');
  const traditional = data.comparisons.filter(c => c.provider !== 'CeloFlow');
  const cheapest = traditional[0];

  return (
    <div className="bg-white dark:bg-gray-700 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-600 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-b border-gray-100 dark:border-gray-600">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-celo-green" />
            <span className="text-xs font-bold text-gray-700 dark:text-gray-200 uppercase tracking-wider">
              {t('Fee Comparison')}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {getConfidenceBadge(data.data_source, data.data_source)}
            {data.last_updated && (
              <span className="text-[9px] text-gray-400">
                {formatTimestamp(data.last_updated)}
              </span>
            )}
            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={isRefreshing}
                className="p-1 rounded-full hover:bg-white/50 dark:hover:bg-gray-600/50 transition-colors disabled:opacity-50"
                title={t('Refresh fees')}
              >
                <RefreshCcw className={`w-3 h-3 text-gray-400 ${isRefreshing ? 'animate-spin' : ''}`} />
              </button>
            )}
          </div>
        </div>

        {/* Savings highlight */}
        {data.savings_vs_most_expensive > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 bg-green-100 dark:bg-green-900/40 rounded-lg px-3 py-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                <span className="text-xs font-bold text-green-700 dark:text-green-300">
                  {t('Save up to')} ${data.savings_vs_most_expensive.toFixed(2)}
                </span>
              </div>
              <span className="text-[10px] text-green-600 dark:text-green-400 font-medium">
                {t('vs')} {traditional[traditional.length - 1]?.provider || t('traditional')}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* CeloFlow highlight */}
      {celoflow && (
        <div className="px-4 py-3 bg-green-50/50 dark:bg-green-900/10 border-b border-gray-100 dark:border-gray-600">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-celo-green/20 flex items-center justify-center">
                <Zap className="w-3 h-3 text-celo-green" />
              </div>
              <div>
                <span className="text-sm font-bold text-gray-900 dark:text-white">CeloFlow</span>
                {data.celoflow_rank === 1 && (
                  <span className="ml-1.5 text-[9px] font-bold bg-celo-green text-white px-1.5 py-0.5 rounded">
                    {t('CHEAPEST')}
                  </span>
                )}
              </div>
            </div>
            <div className="text-right">
              <span className="text-sm font-bold text-celo-green">${celoflow.total_fee.toFixed(2)}</span>
              <span className="text-[10px] text-gray-400 ml-1">({celoflow.fee_percentage}%)</span>
            </div>
          </div>
          <div className="mt-1.5 flex items-center justify-between text-[10px] text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-1">
              {getSpeedIcon(celoflow.speed)}
              <span>{celoflow.speed}</span>
            </div>
            <span>{t('Receives')}: ${celoflow.recipient_receives.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* Provider list (collapsed: top 2, expanded: all) */}
      <div className="divide-y divide-gray-50 dark:divide-gray-600/50">
        {(isExpanded ? traditional : traditional.slice(0, 2)).map((provider, idx) => (
          <div
            key={provider.provider}
            className={`px-4 py-2.5 transition-colors cursor-pointer ${
              selectedProvider === provider.provider
                ? 'bg-gray-50 dark:bg-gray-600/50'
                : 'hover:bg-gray-50/50 dark:hover:bg-gray-600/30'
            }`}
            onClick={() => setSelectedProvider(
              selectedProvider === provider.provider ? null : provider.provider
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-gray-100 dark:bg-gray-600 flex items-center justify-center text-[9px] font-bold text-gray-500 dark:text-gray-300">
                  {(provider.rank || idx + 2)}
                </span>
                <div>
                  <span className="text-xs font-semibold text-gray-700 dark:text-gray-200">
                    {provider.provider}
                  </span>
                  {provider.confidence && (
                    <span className="ml-1">
                      {getConfidenceBadge(provider.confidence, provider.data_source)}
                    </span>
                  )}
                </div>
              </div>
              <div className="text-right flex items-center gap-2">
                <div>
                  <span className="text-xs font-bold text-gray-800 dark:text-gray-100">
                    ${provider.total_fee.toFixed(2)}
                  </span>
                  <span className="text-[9px] text-gray-400 ml-0.5">
                    ({provider.fee_percentage}%)
                  </span>
                </div>
                {celoflow && provider.total_fee > celoflow.total_fee && (
                  <span className="text-[9px] font-bold text-red-500">
                    +${(provider.total_fee - celoflow.total_fee).toFixed(2)}
                  </span>
                )}
              </div>
            </div>

            {/* Speed row */}
            <div className="mt-1 flex items-center justify-between text-[10px] text-gray-400">
              <div className="flex items-center gap-1">
                {getSpeedIcon(provider.speed)}
                <span>{provider.speed}</span>
              </div>
              {provider.fx_markup > 0 && (
                <span>{t('FX markup')}: ${provider.fx_markup.toFixed(2)}</span>
              )}
            </div>

            {/* Expanded breakdown */}
            {selectedProvider === provider.provider && provider.breakdown && (
              <div className="mt-2 pl-7 space-y-1 text-[10px] text-gray-500 dark:text-gray-400 border-l-2 border-gray-200 dark:border-gray-500 animate-fade-in-up">
                {provider.breakdown.transfer_fee !== undefined && (
                  <div className="flex justify-between">
                    <span>{t('Transfer fee')}</span>
                    <span>${provider.breakdown.transfer_fee.toFixed(2)}</span>
                  </div>
                )}
                {provider.breakdown.fx_markup_cost !== undefined && provider.breakdown.fx_markup_cost > 0 && (
                  <div className="flex justify-between">
                    <span>{t('FX markup cost')}</span>
                    <span>${provider.breakdown.fx_markup_cost.toFixed(2)}</span>
                  </div>
                )}
                {provider.exchange_rate !== undefined && provider.exchange_rate > 0 && (
                  <div className="flex justify-between">
                    <span>{t('Exchange rate')}</span>
                    <span>{provider.exchange_rate.toFixed(4)}</span>
                  </div>
                )}
                {provider.mid_market_rate !== undefined && provider.mid_market_rate > 0 && (
                  <div className="flex justify-between">
                    <span>{t('Mid-market rate')}</span>
                    <span>{provider.mid_market_rate.toFixed(4)}</span>
                  </div>
                )}
                <div className="flex justify-between font-medium">
                  <span>{t('Recipient gets')}</span>
                  <span>${provider.recipient_receives.toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Expand/collapse toggle */}
      {traditional.length > 2 && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full px-4 py-2 text-[10px] font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-600/30 transition-colors flex items-center justify-center gap-1 border-t border-gray-50 dark:border-gray-600/50"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="w-3 h-3" />
              {t('Show less')}
            </>
          ) : (
            <>
              <ChevronDown className="w-3 h-3" />
              {t('Show all {{count}} providers', { count: traditional.length })}
            </>
          )}
        </button>
      )}

      {/* Recommendation */}
      {data.recommendation && (
        <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-600">
          <div className="flex items-start gap-2">
            <Shield className="w-3.5 h-3.5 text-celo-green mt-0.5 shrink-0" />
            <p className="text-[10px] text-gray-600 dark:text-gray-300 leading-relaxed">
              {data.recommendation}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
