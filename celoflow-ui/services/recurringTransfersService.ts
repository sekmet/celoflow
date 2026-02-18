import { CELOFLOW_API_URL } from '../lib/celoflow-client';

export interface ScheduledTransfer {
  id: string;
  recipient: string;
  amount: string;
  currency: string;
  frequency: string;
  next_run: string;
  user_id: string;
  isActive?: boolean;
  createdAt?: string;
  lastExecuted?: string;
  executionCount?: number;
}

export interface ScheduleTransferRequest {
  recipient: string;
  amount: string;
  currency: string;
  frequency: string;
  user_id: string;
}

const STORAGE_KEY = 'celoflow_recurring_transfers';

function loadFromStorage(): ScheduledTransfer[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ScheduledTransfer[]) : [];
  } catch {
    return [];
  }
}

function saveToStorage(transfers: ScheduledTransfer[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(transfers));
  } catch {
    // ignore
  }
}

export async function getScheduledTransfers(userId = ''): Promise<ScheduledTransfer[]> {
  try {
    const params = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
    const res = await fetch(`${CELOFLOW_API_URL}/api/transfers/scheduled${params}`);
    if (res.ok) {
      const data = await res.json() as { transfers: ScheduledTransfer[]; count: number };
      saveToStorage(data.transfers);
      return data.transfers;
    }
  } catch {
    // fall through to localStorage
  }
  const stored = loadFromStorage();
  return userId ? stored.filter((t) => t.user_id === userId) : stored;
}

export async function scheduleTransfer(req: ScheduleTransferRequest): Promise<{ success: boolean; message: string; transfer?: ScheduledTransfer }> {
  try {
    const res = await fetch(`${CELOFLOW_API_URL}/api/transfers/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (res.ok) {
      const data = await res.json() as { success: boolean; message: string };
      if (data.success) {
        // Refresh local cache
        await getScheduledTransfers(req.user_id);
      }
      return data;
    }
    const err = await res.json() as { error: string };
    return { success: false, message: err.error ?? 'Failed to schedule transfer' };
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Network error';
    // Optimistic local save
    const localTransfer: ScheduledTransfer = {
      id: `local_${Date.now()}`,
      recipient: req.recipient,
      amount: req.amount,
      currency: req.currency,
      frequency: req.frequency,
      next_run: 'Pending sync',
      user_id: req.user_id,
      isActive: true,
      createdAt: new Date().toISOString(),
      executionCount: 0,
    };
    const stored = loadFromStorage();
    stored.push(localTransfer);
    saveToStorage(stored);
    return { success: true, message: `Saved locally: ${msg}`, transfer: localTransfer };
  }
}

export async function cancelScheduledTransfer(jobId: string): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`${CELOFLOW_API_URL}/api/transfers/scheduled/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
    });
    if (res.ok) {
      const data = await res.json() as { success: boolean; message: string };
      if (data.success) {
        const stored = loadFromStorage().filter((t) => t.id !== jobId);
        saveToStorage(stored);
      }
      return data;
    }
    const err = await res.json() as { error: string };
    return { success: false, message: err.error ?? 'Failed to cancel transfer' };
  } catch {
    // Remove locally
    const stored = loadFromStorage().filter((t) => t.id !== jobId);
    saveToStorage(stored);
    return { success: true, message: 'Cancelled locally' };
  }
}
