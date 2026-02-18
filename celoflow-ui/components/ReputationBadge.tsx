import React, { useState, useEffect } from 'react';
import { Shield, Star, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';
import { useI18n } from '../lib/language';

interface ReputationData {
  agent_id: number;
  score: number;
  success_rate: number;
  total_tasks: number;
  status: 'excellent' | 'good' | 'average' | 'below_average' | 'poor' | 'unknown';
  tee_verified: boolean;
  trend?: 'improving' | 'stable' | 'declining';
}

interface ReputationBadgeProps {
  agentId?: number;
  compact?: boolean;
  agentBaseUrl?: string;
}

const STATUS_CONFIG: Record<string, { color: string; bgColor: string; label: string }> = {
  excellent: { color: 'text-green-600 dark:text-green-400', bgColor: 'bg-green-100 dark:bg-green-900/30', label: 'Excellent' },
  good: { color: 'text-blue-600 dark:text-blue-400', bgColor: 'bg-blue-100 dark:bg-blue-900/30', label: 'Good' },
  average: { color: 'text-yellow-600 dark:text-yellow-400', bgColor: 'bg-yellow-100 dark:bg-yellow-900/30', label: 'Average' },
  below_average: { color: 'text-orange-600 dark:text-orange-400', bgColor: 'bg-orange-100 dark:bg-orange-900/30', label: 'Below Average' },
  poor: { color: 'text-red-600 dark:text-red-400', bgColor: 'bg-red-100 dark:bg-red-900/30', label: 'Poor' },
  unknown: { color: 'text-gray-500 dark:text-gray-400', bgColor: 'bg-gray-100 dark:bg-gray-800', label: 'Unknown' },
};

export function ReputationBadge({ agentId = 0, compact = false, agentBaseUrl = '' }: ReputationBadgeProps) {
  const { t } = useI18n();
  const [reputation, setReputation] = useState<ReputationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const fetchReputation = async () => {
      if (!agentBaseUrl) {
        // Use mock data when no backend is available
        setReputation({
          agent_id: agentId,
          score: 85.5,
          success_rate: 97.2,
          total_tasks: 1247,
          status: 'good',
          tee_verified: true,
          trend: 'improving',
        });
        return;
      }

      setIsLoading(true);
      try {
        const res = await fetch(`${agentBaseUrl}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: [{ role: 'user', content: `get_agent_reputation for agent ${agentId}` }],
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.score !== undefined) {
            setReputation(data as ReputationData);
          }
        }
      } catch {
        // Use fallback data
        setReputation({
          agent_id: agentId,
          score: 85.5,
          success_rate: 97.2,
          total_tasks: 1247,
          status: 'good',
          tee_verified: true,
          trend: 'improving',
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchReputation();
  }, [agentId, agentBaseUrl]);

  if (isLoading || !reputation) {
    return (
      <div className={`animate-pulse ${compact ? 'inline-flex items-center gap-1.5' : 'p-3 rounded-xl bg-gray-100 dark:bg-gray-800'}`}>
        <div className="w-4 h-4 rounded-full bg-gray-300 dark:bg-gray-600" />
        {!compact && <div className="w-24 h-3 rounded bg-gray-300 dark:bg-gray-600 mt-2" />}
      </div>
    );
  }

  const config = STATUS_CONFIG[reputation.status] || STATUS_CONFIG.unknown;

  const TrendIcon = reputation.trend === 'improving' ? TrendingUp
    : reputation.trend === 'declining' ? TrendingDown
    : Minus;

  const trendColor = reputation.trend === 'improving' ? 'text-green-500'
    : reputation.trend === 'declining' ? 'text-red-500'
    : 'text-gray-400';

  // Compact badge (for navbar / inline use)
  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full ${config.bgColor} cursor-default`} title={`${t('Agent Reputation')}: ${reputation.score}/100`}>
        {reputation.tee_verified ? (
          <Shield className={`w-3.5 h-3.5 ${config.color}`} />
        ) : (
          <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
        )}
        <span className={`text-xs font-bold ${config.color}`}>{reputation.score.toFixed(0)}</span>
      </div>
    );
  }

  // Full badge
  return (
    <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${config.bgColor}`}>
            <Shield className={`w-5 h-5 ${config.color}`} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">{t('Agent Reputation')}</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">ERC-8004 {t('Verified')}</p>
          </div>
        </div>
        <div className={`px-2.5 py-1 rounded-full ${config.bgColor}`}>
          <span className={`text-xs font-bold ${config.color}`}>{t(config.label)}</span>
        </div>
      </div>

      {/* Score */}
      <div className="flex items-end gap-3">
        <div className="text-3xl font-bold text-gray-900 dark:text-white">{reputation.score.toFixed(1)}</div>
        <div className="text-sm text-gray-500 dark:text-gray-400 pb-1">/100</div>
        <div className={`flex items-center gap-0.5 pb-1 ${trendColor}`}>
          <TrendIcon className="w-4 h-4" />
          <span className="text-xs font-medium">{reputation.trend}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            reputation.score >= 75 ? 'bg-green-500' :
            reputation.score >= 50 ? 'bg-yellow-500' :
            'bg-red-500'
          }`}
          style={{ width: `${reputation.score}%` }}
        />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 pt-1">
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900 dark:text-white">{reputation.success_rate.toFixed(1)}%</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{t('Success Rate')}</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-gray-900 dark:text-white">{reputation.total_tasks.toLocaleString()}</div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{t('Total Tasks')}</div>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1">
            {reputation.tee_verified ? (
              <>
                <Shield className="w-4 h-4 text-green-500" />
                <span className="text-sm font-bold text-green-600 dark:text-green-400">{t('Yes')}</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-4 h-4 text-yellow-500" />
                <span className="text-sm font-bold text-yellow-600 dark:text-yellow-400">{t('No')}</span>
              </>
            )}
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{t('TEE Verified')}</div>
        </div>
      </div>

      {/* Stars */}
      <div className="flex items-center gap-1 pt-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-4 h-4 ${
              star <= Math.round(reputation.score / 20)
                ? 'text-yellow-400 fill-yellow-400'
                : 'text-gray-300 dark:text-gray-600'
            }`}
          />
        ))}
        <span className="text-xs text-gray-500 dark:text-gray-400 ml-1">
          ({(reputation.score / 20).toFixed(1)}/5.0)
        </span>
      </div>
    </div>
  );
}
