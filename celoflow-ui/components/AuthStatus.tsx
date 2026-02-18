import React, { useState, useEffect, useCallback } from 'react';
import { Shield, ShieldCheck, ShieldAlert, LogOut, RefreshCw, Loader2 } from 'lucide-react';
import { authService, AuthState } from '../lib/auth-service';
import { useI18n } from '../lib/language';

interface AuthStatusProps {
  walletAddress?: string;
}

export function AuthStatus({ walletAddress }: AuthStatusProps) {
  const [authState, setAuthState] = useState<AuthState>(authService.getState());
  const [isLoading, setIsLoading] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  // Auto-login on mount and when wallet connects
  useEffect(() => {
    if (!authState.authenticated) {
      handleLogin();
    }
  }, []); // Only run on mount

  // Re-authenticate when wallet connects
  useEffect(() => {
    if (walletAddress && !authState.authenticated) {
      handleLogin();
    }
  }, [walletAddress, authState.authenticated]);

  const handleLogin = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.login({
        walletAddress: walletAddress || undefined,
      });
    } catch {
      // Silent failure — origin-based auth may not be available
      console.debug('Auth login attempt failed — API may not require auth');
    } finally {
      setIsLoading(false);
    }
  }, [walletAddress]);

  const handleLogout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.logout();
    } finally {
      setIsLoading(false);
      setShowMenu(false);
    }
  }, []);

  const handleClearData = useCallback(() => {
    authService.clearStoredData();
    setShowMenu(false);
  }, []);

  const handleRefresh = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.refresh();
    } finally {
      setIsLoading(false);
    }
  }, []);

  if (isLoading) {
    return (
      <div className="p-2 rounded-full text-gray-400 dark:text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  if (!authState.authenticated) {
    return (
      <button
        onClick={handleLogin}
        className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-400 dark:text-gray-500"
        title={t('Connect to API')}
      >
        <ShieldAlert className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        title={authState.teeVerified ? t('TEE Verified') : t('Authenticated')}
      >
        {authState.teeVerified ? (
          <ShieldCheck className="w-6 h-6 text-green-500" />
        ) : (
          <Shield className="w-6 h-6 text-blue-500" />
        )}
      </button>

      {showMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full mt-2 z-50 w-56 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 p-3 space-y-2 animate-fade-in-up">
            <div className="text-xs text-gray-500 dark:text-gray-400 font-medium px-2 pb-1 border-b border-gray-100 dark:border-gray-700">
              {t('Authentication')}
            </div>

            <div className="px-2 py-1 text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                <span className="text-gray-700 dark:text-gray-300">{t('Connected')}</span>
              </div>
              {authState.teeVerified && (
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-6 h-6 text-green-500" />
                  <span className="text-green-600 dark:text-green-400">{t('TEE Verified')}</span>
                </div>
              )}
              <div className="text-gray-400 dark:text-gray-500">
                {t('Method')}: {authState.method || 'origin'}
              </div>
            </div>

            <div className="border-t border-gray-100 dark:border-gray-700 pt-2 space-y-1">
              <button
                onClick={handleRefresh}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <RefreshCw className="w-6 h-6" />
                {t('Refresh Token')}
              </button>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
              >
                <LogOut className="w-6 h-6" />
                {t('Disconnect')}
              </button>
              <button
                onClick={handleClearData}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/20 rounded-lg transition-colors"
              >
                <ShieldAlert className="w-6 h-6" />
                {t('Clear Data')}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
