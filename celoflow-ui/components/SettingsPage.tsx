import React, { useState, useEffect } from 'react';
import { X, Bell, Shield, Globe, Palette, DollarSign, ToggleLeft, ToggleRight, ChevronRight, Save, Loader2 } from 'lucide-react';
import { useI18n } from '../lib/language';
import { getUserSettings, updateUserSettings, UserSettings } from '../services/userSettingsService';

interface SettingsPageProps {
  userId?: string;
  onClose?: () => void;
}

const CURRENCIES = ['USDm', 'EURm', 'BRLm', 'PHPm', 'XOFm', 'KESm', 'CELO', 'USDt', 'axlUSDC'];
const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'es', label: 'Español' },
  { code: 'pt', label: 'Português' },
  { code: 'fr', label: 'Français' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'tl', label: 'Filipino' },
];
const THEMES: Array<{ value: UserSettings['theme']; label: string }> = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'auto', label: 'System' },
];

function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
        enabled ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'
      }`}
      aria-pressed={enabled}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

export function SettingsPage({ userId = 'default', onClose }: SettingsPageProps) {
  const { t } = useI18n();
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeSection, setActiveSection] = useState<string>('general');

  useEffect(() => {
    getUserSettings(userId).then(setSettings);
  }, [userId]);

  const handleUpdate = <K extends keyof UserSettings>(key: K, value: UserSettings[K]) => {
    setSettings((prev) => prev ? { ...prev, [key]: value } : prev);
  };

  const handleNotificationUpdate = (key: keyof UserSettings['notifications'], value: boolean) => {
    setSettings((prev) =>
      prev ? { ...prev, notifications: { ...prev.notifications, [key]: value } } : prev,
    );
  };

  const handlePrivacyUpdate = (key: keyof UserSettings['privacy'], value: boolean) => {
    setSettings((prev) =>
      prev ? { ...prev, privacy: { ...prev.privacy, [key]: value } } : prev,
    );
  };

  const handleSave = async () => {
    if (!settings) return;
    setIsSaving(true);
    try {
      await updateUserSettings(userId, settings);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } finally {
      setIsSaving(false);
    }
  };

  if (!settings) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div className="bg-white dark:bg-gray-900 rounded-2xl p-8 flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-green-500" />
          <span className="text-gray-700 dark:text-gray-300">{t('Loading settings...')}</span>
        </div>
      </div>
    );
  }

  const sections = [
    { id: 'general', label: t('General'), icon: <Globe className="w-4 h-4" /> },
    { id: 'transfers', label: t('Transfers'), icon: <DollarSign className="w-4 h-4" /> },
    { id: 'notifications', label: t('Notifications'), icon: <Bell className="w-4 h-4" /> },
    { id: 'privacy', label: t('Privacy'), icon: <Shield className="w-4 h-4" /> },
    { id: 'appearance', label: t('Appearance'), icon: <Palette className="w-4 h-4" /> },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">{t('Settings')}</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600 disabled:opacity-50 transition-colors"
            >
              {isSaving ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : saveSuccess ? (
                <span>✓</span>
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              {saveSuccess ? t('Saved!') : t('Save')}
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-500"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Mobile Tab Navigation */}
        <div className="md:hidden border-b border-gray-200 dark:border-gray-700">
          <div className="flex overflow-x-auto scrollbar-hide px-2 py-2 gap-1">
            {sections.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors whitespace-nowrap shrink-0 ${
                  activeSection === s.id
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
              >
                {s.icon}
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Desktop Sidebar */}
          <nav className="hidden md:block w-44 border-r border-gray-200 dark:border-gray-700 p-3 space-y-1 shrink-0">
            {sections.map((s) => (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left ${
                  activeSection === s.id
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
              >
                {s.icon}
                {s.label}
                {activeSection === s.id && <ChevronRight className="w-3 h-3 ml-auto" />}
              </button>
            ))}
          </nav>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 md:space-y-6">
            {/* General */}
            {activeSection === 'general' && (
              <div className="space-y-4 md:space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    {t('Language')}
                  </label>
                  <select
                    value={settings.language}
                    onChange={(e) => handleUpdate('language', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:border-green-500 outline-none"
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l.code} value={l.code}>{l.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Transfers */}
            {activeSection === 'transfers' && (
              <div className="space-y-4 md:space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    {t('Default Currency')}
                  </label>
                  <select
                    value={settings.defaultCurrency}
                    onChange={(e) => handleUpdate('defaultCurrency', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-white focus:border-green-500 outline-none"
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center justify-between p-3 md:p-4 rounded-xl border border-gray-200 dark:border-gray-700">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{t('Show Fee Comparison')}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {t('Compare CeloFlow fees with traditional providers before transfers')}
                    </p>
                  </div>
                  <Toggle
                    enabled={settings.showFeeComparison}
                    onToggle={() => handleUpdate('showFeeComparison', !settings.showFeeComparison)}
                  />
                </div>
              </div>
            )}

            {/* Notifications */}
            {activeSection === 'notifications' && (
              <div className="space-y-3 md:space-y-4">
                {(
                  [
                    { key: 'transfers' as const, label: t('Transfer Confirmations'), desc: t('Get notified when transfers complete') },
                    { key: 'recurring' as const, label: t('Recurring Transfer Alerts'), desc: t('Notifications for scheduled transfer executions') },
                    { key: 'failures' as const, label: t('Failure Alerts'), desc: t('Get notified when a transfer fails') },
                  ] as const
                ).map(({ key, label, desc }) => (
                  <div key={key} className="flex items-center justify-between p-3 md:p-4 rounded-xl border border-gray-200 dark:border-gray-700">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{label}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{desc}</p>
                    </div>
                    <Toggle
                      enabled={settings.notifications[key]}
                      onToggle={() => handleNotificationUpdate(key, !settings.notifications[key])}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Privacy */}
            {activeSection === 'privacy' && (
              <div className="space-y-3 md:space-y-4">
                <div className="flex items-center justify-between p-3 md:p-4 rounded-xl border border-gray-200 dark:border-gray-700">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{t('Save Transaction History')}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {t('Store your transfer history locally for reference')}
                    </p>
                  </div>
                  <Toggle
                    enabled={settings.privacy.saveHistory}
                    onToggle={() => handlePrivacyUpdate('saveHistory', !settings.privacy.saveHistory)}
                  />
                </div>
                <div className="flex items-center justify-between p-3 md:p-4 rounded-xl border border-gray-200 dark:border-gray-700">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{t('Share Analytics')}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {t('Help improve CeloFlow by sharing anonymous usage data')}
                    </p>
                  </div>
                  <Toggle
                    enabled={settings.privacy.shareAnalytics}
                    onToggle={() => handlePrivacyUpdate('shareAnalytics', !settings.privacy.shareAnalytics)}
                  />
                </div>
              </div>
            )}

            {/* Appearance */}
            {activeSection === 'appearance' && (
              <div className="space-y-4 md:space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                    {t('Theme')}
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {THEMES.map((theme) => (
                      <button
                        key={theme.value}
                        onClick={() => handleUpdate('theme', theme.value)}
                        className={`px-4 py-3 rounded-xl border-2 text-sm font-medium transition-colors ${
                          settings.theme === theme.value
                            ? 'border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                            : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600'
                        }`}
                      >
                        {theme.value === 'light' && '☀️ '}
                        {theme.value === 'dark' && '🌙 '}
                        {theme.value === 'auto' && '⚙️ '}
                        {theme.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer hint */}
        <div className="px-4 md:px-6 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center gap-2">
          {settings.showFeeComparison ? (
            <ToggleRight className="w-4 h-4 text-green-500 shrink-0" />
          ) : (
            <ToggleLeft className="w-4 h-4 text-gray-400 shrink-0" />
          )}
          <span className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
            {settings.showFeeComparison
              ? t('Fee comparison is enabled — you will see provider comparisons before transfers')
              : t('Fee comparison is disabled')}
          </span>
        </div>
      </div>
    </div>
  );
}
