import React, { useState, useEffect, useCallback, useRef } from 'react';
import { X, Send, Wallet, ChevronDown, Search, Star, Loader2, CheckCircle2, AlertCircle, ArrowRight, Zap } from 'lucide-react';
import { useAccount } from 'wagmi';
import { useUserSigning } from '../hooks/useUserSigning';
import { getContacts } from '../services/contactsService';
import { getExchangeRate } from '../services/currencyService';
import { addTransaction } from '../services/transactionHistoryService';
import { Contact, TransactionHistoryItem } from '../types';
import { SUPPORTED_CURRENCIES } from '../constants';
import { useI18n } from '../lib/language';

interface QuickTransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTransferComplete?: (result: TransferCompletedResult) => void;
  defaultRecipient?: string;
  defaultAmount?: number;
  defaultToken?: string;
}

export interface TransferCompletedResult {
  txHash: string;
  recipient: string;
  amount: number;
  token: string;
  explorerUrl: string;
}

interface RecipientOption {
  label: string;
  address: string;
  subtitle: string;
  isFavorite: boolean;
}

function formatAddress(address: string): string {
  if (!address || address.length < 10) return address;
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

function isValidAddress(value: string): boolean {
  return /^0x[0-9a-fA-F]{40}$/.test(value.trim());
}

const QUICK_TOKENS = ['CELO', 'USDm', 'EURm', 'BRLm', 'KESm', 'PHPm', 'COPm', 'GBPm', 'CADm', 'AUDm', 'ZARm', 'GHSm', 'NGNm', 'JPYm', 'CHFm', 'USDT'];

export const QuickTransferModal: React.FC<QuickTransferModalProps> = ({
  isOpen,
  onClose,
  onTransferComplete,
  defaultRecipient = '',
  defaultAmount,
  defaultToken = 'USDm',
}) => {
  const { address, isConnected } = useAccount();
  const { t } = useI18n();
  const userSigning = useUserSigning();

  const [recipientInput, setRecipientInput] = useState(defaultRecipient);
  const [resolvedAddress, setResolvedAddress] = useState('');
  const [amount, setAmount] = useState(defaultAmount ? String(defaultAmount) : '');
  const [token, setToken] = useState(defaultToken);
  const [memo, setMemo] = useState('');
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [filteredContacts, setFilteredContacts] = useState<RecipientOption[]>([]);
  const [showContactDropdown, setShowContactDropdown] = useState(false);
  const [showTokenDropdown, setShowTokenDropdown] = useState(false);
  const [exchangeRate, setExchangeRate] = useState<number | null>(null);
  const [isLoadingRate, setIsLoadingRate] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [step, setStep] = useState<'form' | 'confirm' | 'success'>('form');
  const [txResult, setTxResult] = useState<TransferCompletedResult | null>(null);

  const recipientRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    getContacts()
      .then((all) => setContacts(all.filter((c) => !c.blocked)))
      .catch((err) => console.warn('QuickTransferModal: failed to load contacts', err));
  }, [isOpen]);

  useEffect(() => {
    const q = recipientInput.toLowerCase().trim();
    const source = q
      ? contacts.filter(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.address.toLowerCase().includes(q) ||
            c.country.toLowerCase().includes(q),
        )
      : contacts;
    setFilteredContacts(
      source.slice(0, 8).map((c) => ({
        label: c.name,
        address: c.address,
        subtitle: `${c.city ? c.city + ', ' : ''}${c.country} · ${formatAddress(c.address)}`,
        isFavorite: c.favorite,
      })),
    );
  }, [recipientInput, contacts]);

  useEffect(() => {
    if (isValidAddress(recipientInput)) {
      setResolvedAddress(recipientInput.trim());
    } else {
      const contact = contacts.find(
        (c) => c.name.toLowerCase() === recipientInput.toLowerCase().trim(),
      );
      setResolvedAddress(contact ? contact.address : '');
    }
  }, [recipientInput, contacts]);

  useEffect(() => {
    if (!amount || !token || isNaN(Number(amount))) {
      setExchangeRate(null);
      return;
    }
    const controller = new AbortController();
    setIsLoadingRate(true);
    getExchangeRate(token, 'USD')
      .then(({ rate }) => { if (!controller.signal.aborted) setExchangeRate(rate); })
      .catch(() => { if (!controller.signal.aborted) setExchangeRate(null); })
      .finally(() => { if (!controller.signal.aborted) setIsLoadingRate(false); });
    return () => controller.abort();
  }, [amount, token]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowContactDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen) {
      setRecipientInput(defaultRecipient);
      setAmount(defaultAmount ? String(defaultAmount) : '');
      setToken(defaultToken);
      setMemo('');
      setValidationError('');
      setStep('form');
      setTxResult(null);
      userSigning.reset();
      setTimeout(() => recipientRef.current?.focus(), 100);
    }
  }, [isOpen]); // eslint-disable-line react-hooks/exhaustive-deps

  const validate = useCallback((): boolean => {
    if (!resolvedAddress && !isValidAddress(recipientInput)) {
      setValidationError(t('Please enter a valid wallet address or select a contact.'));
      return false;
    }
    if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) {
      setValidationError(t('Please enter a valid amount greater than 0.'));
      return false;
    }
    if (!isConnected || !address) {
      setValidationError(t('Please connect your wallet to send funds.'));
      return false;
    }
    setValidationError('');
    return true;
  }, [resolvedAddress, recipientInput, amount, isConnected, address, t]);

  const handleSelectContact = (option: RecipientOption) => {
    setRecipientInput(option.label);
    setResolvedAddress(option.address);
    setShowContactDropdown(false);
    setValidationError('');
  };

  const handleProceedToConfirm = async () => {
    if (!validate()) return;
    const target = resolvedAddress || recipientInput.trim();
    try {
      await userSigning.prepare(target, Number(amount), token);
      setStep('confirm');
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : 'Failed to prepare transfer');
    }
  };

  const handleExecute = async () => {
    const result = await userSigning.signAndExecute();
    if (result && result.status === 'success') {
      const completed: TransferCompletedResult = {
        txHash: result.tx_hash ?? '',
        recipient: resolvedAddress || recipientInput.trim(),
        amount: Number(amount),
        token,
        explorerUrl: result.explorer_url ?? '',
      };
      addTransaction(
        {
          amount: Number(amount),
          currency: token,
          recipient: recipientInput.trim(),
          recipientCurrency: token,
          convertedAmount: Number(amount),
          fees: 0,
          savings: 0,
          route: [token],
          frequency: 'one-time',
        },
        'completed' as TransactionHistoryItem['status'],
      );
      setTxResult(completed);
      setStep('success');
      onTransferComplete?.(completed);
    }
  };

  const usdEstimate =
    exchangeRate && amount && !isNaN(Number(amount))
      ? (Number(amount) * exchangeRate).toFixed(2)
      : null;

  const recipientDisplay = recipientInput.trim() || (resolvedAddress ? formatAddress(resolvedAddress) : '');
  const isFormValid = (resolvedAddress || isValidAddress(recipientInput)) && Number(amount) > 0 && isConnected;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full sm:max-w-md bg-white dark:bg-gray-800 sm:rounded-2xl rounded-t-2xl shadow-2xl border border-gray-100 dark:border-gray-700 overflow-hidden animate-fade-in-up">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-celo-green/10 flex items-center justify-center">
              <Wallet className="w-4 h-4 text-celo-green" />
            </div>
            <div>
              <h2 className="font-bold text-gray-900 dark:text-white text-sm">{t('Send with Your Wallet')}</h2>
              {address && <p className="text-[10px] text-gray-400">{formatAddress(address)}</p>}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* FORM STEP */}
        {step === 'form' && (
          <div className="p-5 space-y-4">
            <div ref={dropdownRef} className="relative">
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">{t('Recipient')}</label>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
                <input
                  ref={recipientRef}
                  type="text"
                  value={recipientInput}
                  onChange={(e) => { setRecipientInput(e.target.value); setShowContactDropdown(true); setValidationError(''); }}
                  onFocus={() => setShowContactDropdown(true)}
                  placeholder={t('Name, address, or 0x...')}
                  className="w-full pl-9 pr-9 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-900 dark:text-white placeholder-gray-400 outline-none focus:ring-2 focus:ring-celo-green/30 focus:border-celo-green transition-all"
                />
                {resolvedAddress && <CheckCircle2 className="absolute right-3 top-2.5 w-4 h-4 text-green-500" />}
              </div>
              {showContactDropdown && filteredContacts.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl shadow-lg overflow-hidden max-h-48 overflow-y-auto">
                  {filteredContacts.map((opt) => (
                    <button key={opt.address} onClick={() => handleSelectContact(opt)} className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors text-left">
                      <div className="w-7 h-7 rounded-full bg-celo-green/10 flex items-center justify-center shrink-0">
                        <span className="text-xs font-bold text-celo-green">{opt.label.charAt(0).toUpperCase()}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{opt.label}</span>
                          {opt.isFavorite && <Star className="w-3 h-3 text-yellow-400 fill-yellow-400 shrink-0" />}
                        </div>
                        <p className="text-[10px] text-gray-400 truncate">{opt.subtitle}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">{t('Amount')}</label>
              <div className="flex gap-2">
                <input
                  type="number" min="0" step="any" value={amount}
                  onChange={(e) => { setAmount(e.target.value); setValidationError(''); }}
                  placeholder="0.00"
                  className="flex-1 px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-900 dark:text-white placeholder-gray-400 outline-none focus:ring-2 focus:ring-celo-green/30 focus:border-celo-green transition-all"
                />
                <div className="relative">
                  <button onClick={() => setShowTokenDropdown(!showTokenDropdown)} className="flex items-center gap-1.5 px-3 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl text-sm font-bold text-gray-700 dark:text-gray-200 hover:border-celo-green transition-colors min-w-[90px] justify-between">
                    <span>{token}</span>
                    <ChevronDown className={`w-3 h-3 transition-transform ${showTokenDropdown ? 'rotate-180' : ''}`} />
                  </button>
                  {showTokenDropdown && (
                    <div className="absolute right-0 top-full mt-1 z-20 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl shadow-lg overflow-hidden max-h-48 overflow-y-auto min-w-[120px]">
                      {SUPPORTED_CURRENCIES.filter((c) => QUICK_TOKENS.includes(c)).map((c) => (
                        <button key={c} onClick={() => { setToken(c); setShowTokenDropdown(false); }} className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors ${token === c ? 'font-bold text-celo-green' : 'text-gray-700 dark:text-gray-200'}`}>{c}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {amount && Number(amount) > 0 && (
                <p className="text-[10px] text-gray-400 mt-1 pl-1">
                  {isLoadingRate ? <span className="flex items-center gap-1"><Loader2 className="w-2.5 h-2.5 animate-spin" />{t('Calculating...')}</span> : usdEstimate ? `≈ $${usdEstimate} USD` : null}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">
                {t('Note')} <span className="font-normal normal-case text-gray-400">({t('optional')})</span>
              </label>
              <input type="text" value={memo} onChange={(e) => setMemo(e.target.value)} placeholder={t('e.g. Rent payment, Birthday gift...')} maxLength={120} className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-900 dark:text-white placeholder-gray-400 outline-none focus:ring-2 focus:ring-celo-green/30 focus:border-celo-green transition-all" />
            </div>

            {validationError && (
              <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-xs bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded-lg">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" /><span>{validationError}</span>
              </div>
            )}
            {!isConnected && (
              <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs bg-amber-50 dark:bg-amber-900/20 px-3 py-2 rounded-lg">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" /><span>{t('Connect your wallet to use this feature.')}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-[10px] text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-3 py-1.5 rounded-lg">
              <Zap className="w-3 h-3" /><span>{t('Powered by Celo · < 5 second settlement')}</span>
            </div>

            <button onClick={handleProceedToConfirm} disabled={!isFormValid || userSigning.isLoading} className="w-full py-3 bg-celo-green hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-all active:scale-95 shadow-lg shadow-green-500/20 flex items-center justify-center gap-2">
              {userSigning.isLoading ? <><Loader2 className="w-4 h-4 animate-spin" />{t('Preparing...')}</> : <>{t('Review Transfer')}<ArrowRight className="w-4 h-4" /></>}
            </button>
          </div>
        )}

        {/* CONFIRM STEP */}
        {step === 'confirm' && userSigning.preparedTransfer && (
          <div className="p-5 space-y-4">
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 space-y-3">
              <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{t('Transfer Summary')}</h3>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('To')}</span>
                <span className="text-sm font-bold text-gray-900 dark:text-white">{recipientDisplay}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('Amount')}</span>
                <span className="text-sm font-bold text-celo-green">{amount} {token}</span>
              </div>
              {usdEstimate && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('Est. Value')}</span>
                  <span className="text-xs text-gray-400">≈ ${usdEstimate} USD</span>
                </div>
              )}
              {userSigning.preparedTransfer.estimated_gas_cost_eth > 0 && (
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('Est. Gas')}</span>
                  <span className="text-xs text-gray-400">{userSigning.preparedTransfer.estimated_gas_cost_eth.toFixed(6)} CELO</span>
                </div>
              )}
              {memo && (
                <div className="flex justify-between items-start">
                  <span className="text-sm text-gray-500 dark:text-gray-400">{t('Note')}</span>
                  <span className="text-xs text-gray-600 dark:text-gray-300 text-right max-w-[60%]">{memo}</span>
                </div>
              )}
              <div className="flex justify-between items-center pt-2 border-t border-gray-200 dark:border-gray-600">
                <span className="text-sm text-gray-500 dark:text-gray-400">{t('Signed by')}</span>
                <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                  <Wallet className="w-3 h-3" /><span>{t('Your wallet')}</span>
                </div>
              </div>
            </div>

            {(userSigning.step === 'failed' || userSigning.step === 'rejected') && userSigning.error && (
              <div className="flex items-center gap-2 text-red-600 dark:text-red-400 text-xs bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded-lg">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" /><span>{userSigning.error}</span>
              </div>
            )}

            <div className="flex gap-2">
              <button onClick={() => { setStep('form'); userSigning.reset(); }} className="flex-1 py-2.5 border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 font-medium rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm">{t('Back')}</button>
              <button onClick={handleExecute} disabled={userSigning.isLoading} className="flex-1 py-2.5 bg-celo-green hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-all active:scale-95 flex items-center justify-center gap-2 text-sm">
                {userSigning.isLoading ? <><Loader2 className="w-4 h-4 animate-spin" />{userSigning.step === 'awaiting_signature' ? t('Waiting for signature...') : t('Broadcasting...')}</> : <><Send className="w-4 h-4" />{t('Sign & Send')}</>}
              </button>
            </div>
          </div>
        )}

        {/* SUCCESS STEP */}
        {step === 'success' && txResult && (
          <div className="p-5 flex flex-col items-center text-center space-y-4">
            <div className="w-14 h-14 bg-green-500 rounded-full flex items-center justify-center shadow-lg shadow-green-500/20">
              <CheckCircle2 className="w-7 h-7 text-white" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white text-lg">{t('Transfer Sent!')}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {t('{{amount}} {{token}} sent to {{recipient}}', { amount: txResult.amount, token: txResult.token, recipient: recipientDisplay })}
              </p>
            </div>
            <div className="w-full bg-gray-50 dark:bg-gray-700/50 rounded-xl p-3 text-left space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">{t('Tx Hash')}</span>
                <span className="font-mono text-gray-600 dark:text-gray-300">{formatAddress(txResult.txHash)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">{t('Network')}</span>
                <span className="text-gray-600 dark:text-gray-300">Celo Sepolia</span>
              </div>
            </div>
            <div className="flex gap-2 w-full">
              {txResult.explorerUrl && (
                <a href={txResult.explorerUrl} target="_blank" rel="noopener noreferrer" className="flex-1 py-2 text-xs font-bold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg flex items-center justify-center bg-white dark:bg-gray-800 transition-colors">
                  {t('View on CeloScan')}
                </a>
              )}
              <button onClick={onClose} className="flex-1 py-2 text-xs font-bold text-white bg-celo-green hover:bg-green-500 rounded-lg transition-colors">{t('Done')}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
