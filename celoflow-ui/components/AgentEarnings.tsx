import React, { useState, useEffect, useCallback } from 'react';
import { TrendingUp, Award, Zap, RefreshCcw, ChevronDown, ChevronUp, DollarSign, Clock } from 'lucide-react';
import { useI18n } from '../lib/language';
import { CELOFLOW_API_URL } from '../lib/celoflow-client';
interface RecentPayment {
  timestamp: number;
  reward_amount: number;
  transfer_amount: number;
  tx_hash?: string;
  payment_id?: string;
}

interface AgentEarningsData {
  agent_id: number;
  total_earned: number;
  currency: string;
  daily_earned: number;
  daily_cap: number;
  total_transfers_rewarded: number;
  reputation_score: number;
  tier: string;
  multiplier: number;
  recent_payments: RecentPayment[];
  error?: string;
}

const TIER_COLORS: Record<string, string> = {
  excellent: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30',
  good: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30',
  average: 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30',
  below_average: 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/30',
  poor: 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30',
};

const TIER_LABELS: Record<string, string> = {
  excellent: 'Excellent',
  good: 'Good',
  average: 'Average',
  below_average: 'Below Avg',
  poor: 'Poor',
};

export const AgentEarnings: React.FC = () => {
  const { t } = useI18n();
  const [earnings, setEarnings] = useState<AgentEarningsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEarnings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${CELOFLOW_API_URL}/api/agent/earnings`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      if (response.ok) {
        const data = await response.json() as AgentEarningsData;
        setEarnings(data);
      } else {
        // Fallback: fetch via chat tool
        const chatResponse = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: 'get_agent_earnings', user_id: 'system' }),
        });
        if (chatResponse.ok) {
          const chatData = await chatResponse.json() as { earnings?: AgentEarningsData };
          if (chatData.earnings) setEarnings(chatData.earnings);
        }
      }
    } catch (err) {
      setError('Unable to load earnings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEarnings();
    const interval = setInterval(fetchEarnings, 60_000);
    return () => clearInterval(interval);
  }, [fetchEarnings]);

  const tierColor = earnings ? (TIER_COLORS[earnings.tier] ?? TIER_COLORS.average) : TIER_COLORS.average;
  const tierLabel = earnings ? (TIER_LABELS[earnings.tier] ?? earnings.tier) : '—';

  const dailyPct = earnings && earnings.daily_cap > 0
    ? Math.min(100, (earnings.daily_earned / earnings.daily_cap) * 100)
    : 0;

  return (
    <div className="relative hidden sm:block">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors border border-emerald-200 dark:border-emerald-800"
        title="Agent Earnings"
      >
        <Award className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300 hidden sm:block">
          {earnings ? `${earnings.total_earned.toFixed(4)} ${earnings.currency}` : '—'}
        </span>
        {expanded ? (
          <ChevronUp className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
        ) : (
          <ChevronDown className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
        )}
      </button>

      {expanded && (
        <div className="absolute left-0 top-full mt-2 w-80 bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <Award className="w-4 h-4 text-emerald-500" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">Agent Earnings</span>
            </div>
            <button
              onClick={fetchEarnings}
              disabled={loading}
              className="p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <RefreshCcw className={`w-3.5 h-3.5 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {error ? (
            <div className="px-4 py-3 text-sm text-red-500">{error}</div>
          ) : !earnings ? (
            <div className="px-4 py-6 text-center text-sm text-gray-400">
              <div className="animate-pulse">Loading earnings...</div>
            </div>
          ) : (
            <>
              {/* Total Earned */}
              <div className="px-4 py-3 bg-linear-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20">
                <div className="flex items-end justify-between">
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Total Earned</p>
                    <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">
                      {earnings.total_earned.toFixed(4)}
                      <span className="text-sm font-medium ml-1">{earnings.currency}</span>
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${tierColor}`}>
                      <TrendingUp className="w-3 h-3" />
                      {tierLabel}
                    </span>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {earnings.multiplier}x multiplier
                    </p>
                  </div>
                </div>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-3 divide-x divide-gray-100 dark:divide-gray-800 border-b border-gray-100 dark:border-gray-800">
                <div className="px-3 py-2 text-center">
                  <p className="text-xs text-gray-400 mb-0.5">Transfers</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">
                    {earnings.total_transfers_rewarded}
                  </p>
                </div>
                <div className="px-3 py-2 text-center">
                  <p className="text-xs text-gray-400 mb-0.5">Rep Score</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">
                    {earnings.reputation_score.toFixed(1)}
                  </p>
                </div>
                <div className="px-3 py-2 text-center">
                  <p className="text-xs text-gray-400 mb-0.5">Daily</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">
                    {earnings.daily_earned.toFixed(4)}
                  </p>
                </div>
              </div>

              {/* Daily Cap Progress */}
              <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-800">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-500 dark:text-gray-400">Daily Cap</span>
                  <span className="text-xs text-gray-600 dark:text-gray-300">
                    {earnings.daily_earned.toFixed(2)} / {earnings.daily_cap.toFixed(2)} {earnings.currency}
                  </span>
                </div>
                <div className="h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                    style={{ width: `${dailyPct}%` }}
                  />
                </div>
              </div>

              {/* Recent Payments */}
              {earnings.recent_payments.length > 0 && (
                <div className="px-4 py-2">
                  <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Recent Rewards</p>
                  <div className="space-y-1.5 max-h-36 overflow-y-auto">
                    {earnings.recent_payments.slice(0, 5).map((payment, idx) => (
                      <div key={payment.payment_id ?? idx} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                          <Clock className="w-3 h-3 shrink-0" />
                          <span>{new Date(payment.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          {payment.tx_hash && (
                            <a
                              href={`https://sepolia.celoscan.io/tx/${payment.tx_hash}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:underline truncate max-w-16"
                            >
                              {payment.tx_hash.slice(0, 8)}…
                            </a>
                          )}
                        </div>
                        <div className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                          <DollarSign className="w-3 h-3" />
                          +{payment.reward_amount.toFixed(4)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* x402 Badge */}
              <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/50 flex items-center gap-1.5">
                <Zap className="w-3 h-3 text-yellow-500" />
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Powered by x402 protocol · ERC-8004
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};
