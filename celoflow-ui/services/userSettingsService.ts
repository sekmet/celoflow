import { CELOFLOW_API_URL } from '../lib/celoflow-client';

export interface UserNotificationSettings {
  transfers: boolean;
  recurring: boolean;
  failures: boolean;
}

export interface UserPrivacySettings {
  shareAnalytics: boolean;
  saveHistory: boolean;
}

export interface UserSettings {
  userId: string;
  showFeeComparison: boolean;
  defaultCurrency: string;
  language: string;
  theme: 'light' | 'dark' | 'auto';
  notifications: UserNotificationSettings;
  privacy: UserPrivacySettings;
}

const DEFAULT_SETTINGS: UserSettings = {
  userId: 'default',
  showFeeComparison: true,
  defaultCurrency: 'USDm',
  language: 'en',
  theme: 'auto',
  notifications: {
    transfers: true,
    recurring: true,
    failures: true,
  },
  privacy: {
    shareAnalytics: false,
    saveHistory: true,
  },
};

const STORAGE_KEY = 'celoflow_user_settings';

function loadFromStorage(userId: string): UserSettings {
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY}_${userId}`);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<UserSettings>;
      return {
        ...DEFAULT_SETTINGS,
        ...parsed,
        userId,
        notifications: { ...DEFAULT_SETTINGS.notifications, ...(parsed.notifications ?? {}) },
        privacy: { ...DEFAULT_SETTINGS.privacy, ...(parsed.privacy ?? {}) },
      };
    }
  } catch {
    // ignore
  }
  return { ...DEFAULT_SETTINGS, userId };
}

function saveToStorage(settings: UserSettings): void {
  try {
    localStorage.setItem(`${STORAGE_KEY}_${settings.userId}`, JSON.stringify(settings));
  } catch {
    // ignore
  }
}

export async function getUserSettings(userId = 'default'): Promise<UserSettings> {
  try {
    const res = await fetch(`${CELOFLOW_API_URL}/api/settings?user_id=${encodeURIComponent(userId)}`);
    if (res.ok) {
      const data = await res.json() as UserSettings;
      saveToStorage(data);
      return data;
    }
  } catch {
    // fall through to localStorage
  }
  return loadFromStorage(userId);
}

export async function updateUserSettings(
  userId: string,
  updates: Partial<Omit<UserSettings, 'userId'>>,
): Promise<UserSettings> {
  const current = loadFromStorage(userId);
  const merged: UserSettings = {
    ...current,
    ...updates,
    userId,
    notifications: { ...current.notifications, ...(updates.notifications ?? {}) },
    privacy: { ...current.privacy, ...(updates.privacy ?? {}) },
  };

  saveToStorage(merged);

  try {
    const res = await fetch(`${CELOFLOW_API_URL}/api/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(merged),
    });
    if (res.ok) {
      const data = await res.json() as { success: boolean; settings: UserSettings };
      if (data.success) {
        saveToStorage(data.settings);
        return data.settings;
      }
    }
  } catch {
    // return local merged version
  }
  return merged;
}

export function getSettingsSync(userId = 'default'): UserSettings {
  return loadFromStorage(userId);
}
