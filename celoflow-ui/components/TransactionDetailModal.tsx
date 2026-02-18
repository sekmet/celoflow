import React, { useState } from 'react';
import {
  X, ExternalLink, Copy, CheckCircle2, Shield, Zap,
  TrendingDown, Clock, DollarSign, ChevronDown, ChevronUp,
  Award
} from 'lucide-react';

interface FeeBreakdown {
  network_fee?: number;
  network_fee_currency?: string;
  service_fee?: number;
  service_fee_currency?: string;
  service_fee_tier?: string;
  total_fee_usd?: number;
  total_fee_pct?: number;
}

interface AgentReward {
  payment_id?: string;
  reward_amount?: number;
  currency?: string;
  tier?: string;
}

interface ComparisonSaving {
  provider: string;
  their_fee: number;
  our_fee: number;
  saved: number;
  saved_pct: number;
}

interface TransactionDetail {
  tx_hash: string;
  status: string;
  amount: number;
  token: string;
  recipient: string;
  explorer_url?: string;
  fee_breakdown?: FeeBreakdown;
  agent_reward?: AgentReward;
  comparison_savings?: ComparisonSaving[];
  tee_address?: string;
  preview_id?: string;
  timestamp?: number;
  note?: string;
}

interface TransactionDetailModalProps {
  transaction: TransactionDetail;
  onClose: () => void;
}

export const TransactionDetailModal: React.FC<TransactionDetailModalProps> = ({
  transaction,
  onClose,
}) => {
  const [copiedHash, setCopiedHash] = useState(false);
  const [showSavings, setShowSavings] = useState(false);
  const [showTEEInfo, setShowTEEInfo] = useState(false);

  const copyHash = async () => {
    try {
      await navigator.clipboard.writeText(transaction.tx_hash);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    } catch {
      // clipboard not available
    }
  };

  const isSuccess = transaction.status === 'success';
  const explorerUrl = transaction.explorer_url
    ?? `https://sepolia.celoscan.io/tx/${transaction.tx_hash}`;

  const tierBadgeColor: Record<string, string> = {
    excellent: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    good: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    average: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
    below_average: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    poor: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  };

  const rewardTier = transaction.agent_reward?.tier ?? 'average';
  const rewardBadge = tierBadgeColor[rewardTier] ?? tierBadgeColor.average;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden animate-fade-in-up">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            {isSuccess ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-500" />
            ) : (
              <X className="w-5 h-5 text-red-500" />
            )}
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">
              Transfer {isSuccess ? 'Complete' : 'Failed'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* Transfer Summary */}
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Amount Sent</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {transaction.amount}
                <span className="text-base font-medium ml-1.5 text-emerald-600 dark:text-emerald-400">
                  {transaction.token}
                </span>
              </p>
            </div>
            {transaction.timestamp && (
              <div className="text-right">
                <div className="flex items-center gap-1 text-xs text-gray-400">
                  <Clock className="w-3 h-3" />
                  {new Date(transaction.timestamp * 1000).toLocaleString()}
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            <span>To:</span>
            <span className="font-mono text-gray-800 dark:text-gray-200">
              {transaction.recipient.slice(0, 8)}…{transaction.recipient.slice(-6)}
            </span>
          </div>

          {transaction.note && (
            <p className="mt-1.5 text-xs text-gray-400 italic">{transaction.note}</p>
          )}
        </div>

        {/* Transaction Hash */}
        <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
            Transaction Hash
          </p>
          <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800 rounded-lg px-3 py-2">
            <span className="text-xs font-mono text-gray-700 dark:text-gray-300 truncate flex-1">
              {transaction.tx_hash}
            </span>
            <button
              onClick={copyHash}
              className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors shrink-0"
              title="Copy hash"
            >
              {copiedHash ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <Copy className="w-3.5 h-3.5 text-gray-400" />
              )}
            </button>
            <a
              href={explorerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors shrink-0"
              title="View on explorer"
            >
              <ExternalLink className="w-3.5 h-3.5 text-blue-500" />
            </a>
          </div>
        </div>

        {/* Fee Breakdown */}
        {transaction.fee_breakdown && (
          <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800">
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
              Fee Breakdown
            </p>
            <div className="space-y-1.5 text-sm">
              {transaction.fee_breakdown.network_fee !== undefined && (
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Network fee</span>
                  <span className="font-mono text-gray-700 dark:text-gray-300">
                    ~{transaction.fee_breakdown.network_fee} {transaction.fee_breakdown.network_fee_currency ?? 'CELO'}
                  </span>
                </div>
              )}
              {transaction.fee_breakdown.service_fee !== undefined && (
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-1.5">
                    <span className="text-gray-500 dark:text-gray-400">Service fee (x402)</span>
                    {transaction.fee_breakdown.service_fee_tier && (
                      <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${tierBadgeColor[transaction.fee_breakdown.service_fee_tier] ?? tierBadgeColor.average}`}>
                        {transaction.fee_breakdown.service_fee_tier}
                      </span>
                    )}
                  </div>
                  <span className="font-mono text-gray-700 dark:text-gray-300">
                    {transaction.fee_breakdown.service_fee.toFixed(4)} {transaction.fee_breakdown.service_fee_currency ?? 'USDm'}
                  </span>
                </div>
              )}
              {transaction.fee_breakdown.total_fee_usd !== undefined && (
                <div className="flex justify-between font-semibold border-t border-gray-100 dark:border-gray-800 pt-1.5 mt-1.5">
                  <span className="text-gray-700 dark:text-gray-300">Total fees</span>
                  <span className="font-mono text-gray-900 dark:text-white">
                    {transaction.fee_breakdown.total_fee_usd.toFixed(4)} USD
                    {transaction.fee_breakdown.total_fee_pct !== undefined && (
                      <span className="text-xs font-normal text-gray-500 ml-1">
                        ({transaction.fee_breakdown.total_fee_pct.toFixed(3)}%)
                      </span>
                    )}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Agent Reward */}
        {transaction.agent_reward && transaction.agent_reward.reward_amount !== undefined && (
          <div className="px-5 py-3 border-b border-gray-100 dark:border-gray-800 bg-emerald-50/50 dark:bg-emerald-900/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Award className="w-4 h-4 text-emerald-500" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Agent Reward (x402)</span>
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${rewardBadge}`}>
                  {rewardTier}
                </span>
              </div>
              <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 font-mono">
                +{transaction.agent_reward.reward_amount.toFixed(4)} {transaction.agent_reward.currency ?? 'USDm'}
              </span>
            </div>
            {transaction.agent_reward.payment_id && (
              <p className="text-xs text-gray-400 mt-1 font-mono">
                ID: {transaction.agent_reward.payment_id}
              </p>
            )}
          </div>
        )}

        {/* Savings vs Traditional */}
        {transaction.comparison_savings && transaction.comparison_savings.length > 0 && (
          <div className="border-b border-gray-100 dark:border-gray-800">
            <button
              onClick={() => setShowSavings(!showSavings)}
              className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <TrendingDown className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  Savings vs traditional providers
                </span>
              </div>
              {showSavings ? (
                <ChevronUp className="w-3.5 h-3.5 text-gray-400" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
              )}
            </button>
            {showSavings && (
              <div className="px-5 pb-3 space-y-1.5">
                {transaction.comparison_savings.map((saving) => (
                  <div key={saving.provider} className="flex items-center justify-between text-xs">
                    <span className="text-gray-600 dark:text-gray-400">{saving.provider}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400 line-through font-mono">${saving.their_fee.toFixed(2)}</span>
                      <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                        −${saving.saved.toFixed(2)} ({saving.saved_pct.toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TEE Info */}
        {transaction.tee_address && (
          <div className="border-b border-gray-100 dark:border-gray-800">
            <button
              onClick={() => setShowTEEInfo(!showTEEInfo)}
              className="w-full flex items-center justify-between px-5 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-blue-500" />
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                  TEE execution details
                </span>
              </div>
              {showTEEInfo ? (
                <ChevronUp className="w-3.5 h-3.5 text-gray-400" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
              )}
            </button>
            {showTEEInfo && (
              <div className="px-5 pb-3 space-y-1.5 text-xs text-gray-600 dark:text-gray-400">
                <div className="flex justify-between">
                  <span>TEE Signer</span>
                  <span className="font-mono">{transaction.tee_address.slice(0, 10)}…{transaction.tee_address.slice(-6)}</span>
                </div>
                {transaction.preview_id && (
                  <div className="flex justify-between">
                    <span>Preview ID</span>
                    <span className="font-mono">{transaction.preview_id}</span>
                  </div>
                )}
                <div className="flex items-center gap-1 mt-1 text-blue-600 dark:text-blue-400">
                  <Shield className="w-3 h-3" />
                  <span>Signed inside Intel TDX enclave</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Zap className="w-3 h-3 text-yellow-500" />
            <span className="text-xs text-gray-400">x402 · ERC-8004</span>
          </div>
          <a
            href={explorerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:underline font-medium"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            View on Celoscan
          </a>
        </div>
      </div>
    </div>
  );
};
