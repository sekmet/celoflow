import React, { useState, useEffect } from 'react';
import { Calendar, Clock, Trash2, Plus, RefreshCw, AlertCircle } from 'lucide-react';
import { useI18n } from '../lib/language';

interface ScheduledTransfer {
  id: string;
  recipient: string;
  amount: string;
  currency: string;
  frequency: string;
  next_run: string;
  user_id: string;
}

interface RecurringTransfersProps {
  agentBaseUrl?: string;
  userId?: string;
  onClose?: () => void;
}

export function RecurringTransfers({ agentBaseUrl = '', userId = '', onClose }: RecurringTransfersProps) {
  const { t } = useI18n();
  const [transfers, setTransfers] = useState<ScheduledTransfer[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [recipient, setRecipient] = useState('');
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('USDm');
  const [frequency, setFrequency] = useState('monthly');

  const frequencies = [
    { value: 'daily', label: t('Daily') },
    { value: 'weekly', label: t('Weekly') },
    { value: 'biweekly', label: t('Every 2 Weeks') },
    { value: 'monthly', label: t('Monthly') },
  ];

  const currencies = ['USDm', 'EURm', 'BRLm', 'PHPm', 'XOFm', 'KESm', 'CELO'];

  const fetchTransfers = async () => {
    if (!agentBaseUrl || !userId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${agentBaseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: `list_scheduled_transfers for user ${userId}` }],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.transfers)) {
          setTransfers(data.transfers);
        }
      }
    } catch (e) {
      setError(t('Failed to load scheduled transfers'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTransfers();
  }, [agentBaseUrl, userId]);

  const handleSchedule = async () => {
    if (!recipient || !amount || !currency || !frequency) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${agentBaseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{
            role: 'user',
            content: `Schedule a ${frequency} transfer of ${amount} ${currency} to ${recipient}`,
          }],
        }),
      });
      if (res.ok) {
        setShowForm(false);
        setRecipient('');
        setAmount('');
        await fetchTransfers();
      }
    } catch (e) {
      setError(t('Failed to schedule transfer'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    setIsLoading(true);
    try {
      await fetch(`${agentBaseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: `Cancel scheduled transfer ${jobId}` }],
        }),
      });
      await fetchTransfers();
    } catch (e) {
      setError(t('Failed to cancel transfer'));
    } finally {
      setIsLoading(false);
    }
  };

  const getFrequencyBadgeColor = (freq: string) => {
    switch (freq) {
      case 'daily': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
      case 'weekly': return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
      case 'biweekly': return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300';
      case 'monthly': return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300';
      default: return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/30">
              <Calendar className="w-5 h-5 text-green-600 dark:text-green-400" />
            </div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">{t('Recurring Transfers')}</h2>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchTransfers} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" title={t('Refresh')}>
              <RefreshCw className={`w-4 h-4 text-gray-500 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            {onClose && (
              <button onClick={onClose} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-500">
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {transfers.length === 0 && !isLoading && (
            <div className="text-center py-8">
              <Clock className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400 text-sm">{t('No recurring transfers scheduled')}</p>
              <p className="text-gray-400 dark:text-gray-500 text-xs mt-1">{t('Set up automatic transfers to save time')}</p>
            </div>
          )}

          {transfers.map((transfer) => (
            <div key={transfer.id} className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-green-300 dark:hover:border-green-700 transition-colors">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-gray-900 dark:text-white">{transfer.amount} {transfer.currency}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getFrequencyBadgeColor(transfer.frequency)}`}>
                      {transfer.frequency}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t('To')}: <span className="font-mono text-xs">{transfer.recipient.length > 20 ? `${transfer.recipient.slice(0, 10)}...${transfer.recipient.slice(-8)}` : transfer.recipient}</span>
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    {t('Next')}: {transfer.next_run}
                  </p>
                </div>
                <button
                  onClick={() => handleCancel(transfer.id)}
                  className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-500 transition-colors"
                  title={t('Cancel')}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}

          {/* New Transfer Form */}
          {showForm && (
            <div className="p-4 rounded-xl border-2 border-dashed border-green-300 dark:border-green-700 space-y-3">
              <input
                type="text"
                placeholder={t('Recipient (address or name)')}
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:border-green-500 outline-none"
              />
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder={t('Amount')}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:border-green-500 outline-none"
                />
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:border-green-500 outline-none"
                >
                  {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <select
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:border-green-500 outline-none"
              >
                {frequencies.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
              <div className="flex gap-2">
                <button
                  onClick={handleSchedule}
                  disabled={!recipient || !amount}
                  className="flex-1 px-4 py-2 bg-green-500 text-white rounded-lg font-medium text-sm hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {t('Schedule')}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  {t('Cancel')}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!showForm && (
          <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setShowForm(true)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-500 text-white rounded-xl font-medium text-sm hover:bg-green-600 transition-colors"
            >
              <Plus className="w-4 h-4" />
              {t('New Recurring Transfer')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
