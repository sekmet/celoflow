import { TransactionHistoryItem, TransactionIntent } from '../types';
import { CELOFLOW_API_URL } from '../lib/celoflow-client';

const STORAGE_KEY = 'celoflow_tx_history';

function loadFromStorage(): TransactionHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TransactionHistoryItem[]) : [];
  } catch {
    return [];
  }
}

function saveToStorage(items: TransactionHistoryItem[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // ignore
  }
}

export function getTransactionHistory(): TransactionHistoryItem[] {
  return loadFromStorage();
}

export function addTransaction(intent: TransactionIntent, status: TransactionHistoryItem['status'] = 'processing'): TransactionHistoryItem {
  const item: TransactionHistoryItem = {
    id: `tx_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    date: new Date().toLocaleDateString(),
    intent,
    status,
  };
  const history = loadFromStorage();
  history.unshift(item);
  saveToStorage(history.slice(0, 200));
  return item;
}

export function updateTransactionStatus(id: string, status: TransactionHistoryItem['status']): TransactionHistoryItem | null {
  const history = loadFromStorage();
  const idx = history.findIndex((h) => h.id === id);
  if (idx === -1) return null;
  history[idx] = { ...history[idx], status };
  saveToStorage(history);
  return history[idx];
}

export function cancelTransaction(id: string): boolean {
  const result = updateTransactionStatus(id, 'cancelled');
  return result !== null;
}

export function clearTransactionHistory(): void {
  saveToStorage([]);
}

export async function syncTransactionHistory(userId = ''): Promise<TransactionHistoryItem[]> {
  try {
    const params = userId ? `?user_id=${encodeURIComponent(userId)}&limit=100` : '?limit=100';
    const res = await fetch(`${CELOFLOW_API_URL}/api/transfers/history${params}`);
    if (res.ok) {
      const data = await res.json() as { history: Array<Record<string, unknown>>; count: number };
      const remoteItems: TransactionHistoryItem[] = data.history.map((entry) => ({
        id: String(entry.job_id ?? entry.id ?? `remote_${Date.now()}`),
        date: entry.timestamp ? new Date(String(entry.timestamp)).toLocaleDateString() : new Date().toLocaleDateString(),
        intent: {
          amount: parseFloat(String(entry.amount ?? 0)),
          currency: String(entry.currency ?? 'USDm'),
          recipient: String(entry.recipient ?? ''),
          recipientCurrency: String(entry.currency ?? 'USDm'),
          convertedAmount: parseFloat(String(entry.amount ?? 0)),
          fees: 0,
          savings: 0,
          route: [],
          frequency: String(entry.frequency ?? 'one-time'),
        } satisfies TransactionIntent,
        status: (entry.status === 'executed' ? 'completed' : String(entry.status ?? 'completed')) as TransactionHistoryItem['status'],
      }));

      const local = loadFromStorage();
      const localIds = new Set(local.map((i) => i.id));
      const merged = [...local, ...remoteItems.filter((r) => !localIds.has(r.id))];
      merged.sort((a, b) => b.date.localeCompare(a.date));
      saveToStorage(merged.slice(0, 200));
      return merged;
    }
  } catch {
    // fall through
  }
  return loadFromStorage();
}
