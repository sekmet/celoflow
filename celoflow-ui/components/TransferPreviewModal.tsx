import React, { useState, useEffect, useCallback } from 'react';
import {
  X, ArrowRight, Clock, Zap, TrendingDown, CheckCircle2,
  AlertCircle, RefreshCcw, Shield, ChevronDown, ChevronUp,
  DollarSign, Route
} from 'lucide-react';

interface ProviderComparison {
  name: string;
  total_fee: number;
  fee_percentage: number;
  speed: string;
}

interface TransferFees {
  network_fee: number;
  network_fee_currency: string;
  service_fee: number;
  service_fee_currency: string;
  service_fee_pct: number;
  service_fee_tier: string;
  total_fee_usd: number;
  total_fee_pct: number;
}

interface TransferRoute {
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

interface TEEBalance {
  sufficient: boolean;
  auto_swap_needed: boolean;
  tee_address?: string;
  token?: string;
  balance?: number;
  required?: number;
  deficit?: number;
}

interface SavingsInfo {
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

interface TransferPreview {
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

interface TransferPreviewModalProps {
  previewData: TransferPreview;
  onConfirm: (previewId: string) => void;
  onCancel: () => void;
  isExecuting?: boolean;
}

const TIER_BADGE: Record<string, string> = {
  excellent: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  good: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  average: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
  below_average: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  poor: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
};

export const TransferPreviewModal: React.FC<TransferPreviewModalProps> = ({
  previewData,
  onConfirm,
  onCancel,
  isExecuting = false,
}) => {
  const [secondsLeft, setSecondsLeft] = useState<number>(previewData.expires_in_seconds);
  const [showComparisons, setShowComparisons] = useState(false);
  const [showRoute, setShowRoute] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = previewData.expires_at - Date.now() / 1000;
      setSecondsLeft(Math.max(0, Math.round(remaining)));
    }, 500);
    return () => clearInterval(interval);
  }, [previewData.expires_at]);

  const isExpired = secondsLeft <= 0;
  const timerColor = secondsLeft > 15 ? 'text-green-600 dark:text-green-400' : secondsLeft > 5 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400';

  const tierBadge = TIER_BADGE[previewData.fees.service_fee_tier] ?? TIER_BADGE.average;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden animate-fade-in-up">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-500" />
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">Transfer Preview</h2>
          </div>
          <div className="flex items-center gap-3">
            {/* Countdown timer */}
            <div className={`flex items-center gap-1 text-sm font-mono ${timerColor}`}>
              <Clock className="w-3.5 h-3.5" />
              <span>{secondsLeft}s</span>
            </div>
            <button
              onClick={onCancel}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Transfer Summary */}
        <div className="px-5 py-4 bg-linear-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Sending</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {previewData.amount}
                <span className="text-base font-medium ml-1.5 text-emerald-600 dark:text-emerald-400">
                  {previewData.token}
                </span>
              </p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-400" />
            <div className="text-right">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">To</p>
              <p className="text-sm font-mono text-gray-700 dark:text-gray-300">
                {previewData.recipient.slice(0, 6)}…{previewData.recipient.slice(-4)}
              </p>
              {previewData.destination_country && (
                <p className="text-xs text-gray-500 dark:text-gray-400">{previewData.destination_country}</p>
              )}
            </div>
          </div>
        </div>

        {/* Fee Breakdown */}
        <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Fee Breakdown</p>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">Network fee</span>
              <span className="text-gray-700 dark:text-gray-300 font-mono">
                ~{previewData.fees.network_fee} {previewData.fees.network_fee_currency}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-1.5">
                <span className="text-gray-600 dark:text-gray-400">Service fee (x402)</span>
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${tierBadge}`}>
                  {previewData.fees.service_fee_tier}
                </span>
              </div>
              <span className="text-gray-700 dark:text-gray-300 font-mono">
                {previewData.fees.service_fee.toFixed(4)} {previewData.fees.service_fee_currency}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm font-semibold border-t border-gray-100 dark:border-gray-800 pt-1.5 mt-1.5">
              <span className="text-gray-700 dark:text-gray-300">Total fees</span>
              <span className="text-gray-900 dark:text-white font-mono">
                {previewData.fees.total_fee_usd.toFixed(4)} USD
                <span className="text-xs font-normal text-gray-500 ml-1">
                  ({previewData.fees.total_fee_pct.toFixed(3)}%)
                </span>
              </span>
            </div>
          </div>
        </div>

        {/* Savings vs Traditional */}
        {previewData.savings.available && (previewData.savings.savings_vs_cheapest ?? 0) > 0 && (
          <div className="px-5 py-2.5 bg-emerald-50 dark:bg-emerald-900/20 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span className="text-sm text-emerald-700 dark:text-emerald-300 font-medium">
                Save {previewData.savings.savings_vs_cheapest_pct?.toFixed(1)}% vs {previewData.savings.cheapest_provider}
              </span>
              <span className="text-xs text-emerald-600 dark:text-emerald-400 ml-auto">
                ${previewData.savings.savings_vs_cheapest?.toFixed(2)} saved
              </span>
            </div>
          </div>
        )}

        {/* TEE Auto-swap warning */}
        {previewData.tee_balance.auto_swap_needed && (
          <div className="px-5 py-2.5 bg-yellow-50 dark:bg-yellow-900/20 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-600 dark:text-yellow-400" />
              <span className="text-xs text-yellow-700 dark:text-yellow-300">
                Auto-swap will be triggered: CELO → USDm → {previewData.token}
              </span>
            </div>
          </div>
        )}

        {/* Expandable: Provider Comparisons */}
        {previewData.comparisons.length > 0 && (
          <div className="border-b border-gray-100 dark:border-gray-800">
            <button
              onClick={() => setShowComparisons(!showComparisons)}
              className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                Compare with traditional providers
              </span>
              {showComparisons ? (
                <ChevronUp className="w-3.5 h-3.5 text-gray-400" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
              )}
            </button>
            {showComparisons && (
              <div className="px-5 pb-3 space-y-1.5">
                {/* CeloFlow row */}
                <div className="flex items-center justify-between text-xs bg-emerald-50 dark:bg-emerald-900/20 rounded-lg px-3 py-1.5">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    <span className="font-semibold text-emerald-700 dark:text-emerald-300">CeloFlow</span>
                    <span className="text-emerald-600 dark:text-emerald-400">· Instant</span>
                  </div>
                  <span className="font-mono font-semibold text-emerald-700 dark:text-emerald-300">
                    ${previewData.fees.total_fee_usd.toFixed(4)}
                  </span>
                </div>
                {previewData.comparisons.map((provider) => (
                  <div key={provider.name} className="flex items-center justify-between text-xs px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                    <div>
                      <span className="text-gray-700 dark:text-gray-300">{provider.name}</span>
                      <span className="text-gray-400 ml-1.5">· {provider.speed}</span>
                    </div>
                    <span className="font-mono text-gray-600 dark:text-gray-400">
                      ${provider.total_fee.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Expandable: Route */}
        {previewData.route.available && (
          <div className="border-b border-gray-100 dark:border-gray-800">
            <button
              onClick={() => setShowRoute(!showRoute)}
              className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Route className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  Route: {previewData.route.route_type ?? 'Mento v2'}
                </span>
              </div>
              {showRoute ? (
                <ChevronUp className="w-3.5 h-3.5 text-gray-400" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
              )}
            </button>
            {showRoute && (
              <div className="px-5 pb-3 text-xs space-y-1 text-gray-600 dark:text-gray-400">
                <div className="flex justify-between">
                  <span>Exchange rate</span>
                  <span className="font-mono">1 {previewData.route.from_currency} = {previewData.route.rate?.toFixed(4)} {previewData.route.to_currency}</span>
                </div>
                <div className="flex justify-between">
                  <span>Estimated output</span>
                  <span className="font-mono">{previewData.route.estimated_output?.toFixed(4)} {previewData.route.to_currency}</span>
                </div>
                <div className="flex justify-between">
                  <span>Max slippage</span>
                  <span className="font-mono">{previewData.route.slippage_pct?.toFixed(2)}%</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Expired warning */}
        {isExpired && (
          <div className="px-5 py-2.5 bg-red-50 dark:bg-red-900/20 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-500" />
            <span className="text-sm text-red-600 dark:text-red-400">Preview expired — rates may have changed</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="px-5 py-4 flex gap-3">
          <button
            onClick={onCancel}
            disabled={isExecuting}
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(previewData.preview_id)}
            disabled={isExpired || isExecuting}
            className="flex-1 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {isExecuting ? (
              <>
                <RefreshCcw className="w-4 h-4 animate-spin" />
                Executing…
              </>
            ) : isExpired ? (
              'Expired'
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                Confirm Transfer
              </>
            )}
          </button>
        </div>

        {/* Footer note */}
        <div className="px-5 pb-3 flex items-center gap-1.5">
          <DollarSign className="w-3 h-3 text-gray-400" />
          <span className="text-xs text-gray-400">
            Service fee collected via x402 protocol · ERC-8004 verified agent
          </span>
        </div>
      </div>
    </div>
  );
};
