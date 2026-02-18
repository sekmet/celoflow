/**
 * WalletAuthorizationModal — Modal for choosing between TEE and user wallet signing.
 *
 * Shows transaction details, gas estimates, and lets the user choose
 * how to authorize the transfer.
 */

import React from 'react'
import {
  Shield,
  ShieldCheck,
  Wallet,
  ArrowRight,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Fuel,
  X,
} from 'lucide-react'
import { useI18n } from '../lib/language'
import type { PreparedTransfer } from '../lib/user-signing-client'
import type { SigningStep } from '../hooks/useUserSigning'

interface WalletAuthorizationModalProps {
  isOpen: boolean
  onClose: () => void
  preparedTransfer: PreparedTransfer | null
  signingStep: SigningStep
  error: string | null
  isLoading: boolean
  onChooseTEE: () => void
  onChooseUserWallet: () => void
  onRetryWithTEE: () => void
}

export const WalletAuthorizationModal: React.FC<WalletAuthorizationModalProps> = ({
  isOpen,
  onClose,
  preparedTransfer,
  signingStep,
  error,
  isLoading,
  onChooseTEE,
  onChooseUserWallet,
  onRetryWithTEE,
}) => {
  const { t } = useI18n()

  if (!isOpen) return null

  const transfer = preparedTransfer

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden animate-fade-in-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">
            {signingStep === 'awaiting_choice' && t('Authorize Transfer')}
            {signingStep === 'awaiting_signature' && t('Sign Transaction')}
            {signingStep === 'broadcasting' && t('Broadcasting...')}
            {signingStep === 'confirmed' && t('Transfer Complete')}
            {signingStep === 'failed' && t('Transfer Failed')}
            {signingStep === 'rejected' && t('Transfer Cancelled')}
            {signingStep === 'preparing' && t('Preparing Transfer...')}
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5">
          {/* Transaction Summary */}
          {transfer && (
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {t('Amount')}
                </span>
                <span className="text-lg font-bold text-gray-900 dark:text-white">
                  {transfer.amount} {transfer.resolved_token}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {t('Recipient')}
                </span>
                <span className="text-sm font-mono text-gray-700 dark:text-gray-300">
                  {transfer.recipient_address.slice(0, 6)}...{transfer.recipient_address.slice(-4)}
                </span>
              </div>
              {transfer.needs_auto_swap && (
                <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 p-2 rounded-lg">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>
                    {t('Auto-swap required: CELO → {{token}}', { token: transfer.resolved_token })}
                    {transfer.auto_swap_steps.length > 0 &&
                      ` (${transfer.auto_swap_steps.length} ${t('steps')})`}
                  </span>
                </div>
              )}
              {transfer.estimated_gas_cost_eth > 0 && (
                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                  <span className="flex items-center gap-1">
                    <Fuel className="w-3 h-3" />
                    {t('Est. Gas')}
                  </span>
                  <span>{transfer.estimated_gas_cost_eth.toFixed(6)} CELO</span>
                </div>
              )}
            </div>
          )}

          {/* Choice Buttons */}
          {signingStep === 'awaiting_choice' && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                {t('How would you like to authorize this transfer?')}
              </p>

              {/* User Wallet Option */}
              <button
                onClick={onChooseUserWallet}
                disabled={isLoading}
                className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-celo-green bg-green-50 dark:bg-green-900/10 hover:bg-green-100 dark:hover:bg-green-900/20 transition-colors group"
              >
                <div className="w-12 h-12 rounded-full bg-celo-green/10 flex items-center justify-center shrink-0">
                  <Wallet className="w-6 h-6 text-celo-green" />
                </div>
                <div className="text-left flex-1">
                  <p className="font-bold text-gray-900 dark:text-white">
                    {t('Your Wallet')}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {t('Sign with your connected wallet (MetaMask, etc.)')}
                  </p>
                </div>
                <ArrowRight className="w-5 h-5 text-celo-green opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>

              {/* TEE Agent Wallet Option */}
              <button
                onClick={onChooseTEE}
                disabled={isLoading}
                className="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors group"
              >
                <div className="w-12 h-12 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div className="text-left flex-1">
                  <p className="font-bold text-gray-900 dark:text-white">
                    {t('Agent Wallet')}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {t('Use the secure TEE agent wallet (instant)')}
                  </p>
                </div>
                <ArrowRight className="w-5 h-5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            </div>
          )}

          {/* Awaiting Signature */}
          {signingStep === 'awaiting_signature' && (
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="w-16 h-16 rounded-full bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center animate-pulse">
                <Wallet className="w-8 h-8 text-amber-600 dark:text-amber-400" />
              </div>
              <div className="text-center">
                <p className="font-bold text-gray-900 dark:text-white">
                  {t('Waiting for wallet signature...')}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {t('Please confirm the transaction in your wallet')}
                </p>
              </div>
              <Loader2 className="w-6 h-6 text-celo-green animate-spin" />
            </div>
          )}

          {/* Broadcasting */}
          {signingStep === 'broadcasting' && (
            <div className="flex flex-col items-center gap-4 py-4">
              <Loader2 className="w-12 h-12 text-celo-green animate-spin" />
              <p className="font-bold text-gray-900 dark:text-white">
                {t('Broadcasting transaction...')}
              </p>
            </div>
          )}

          {/* Confirmed */}
          {signingStep === 'confirmed' && (
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
                <CheckCircle2 className="w-10 h-10 text-green-600 dark:text-green-400" />
              </div>
              <div className="text-center">
                <p className="font-bold text-green-700 dark:text-green-400 text-lg">
                  {t('Transfer Authorized!')}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {t('You signed this transfer with your wallet')}
                </p>
              </div>
              <button
                onClick={onClose}
                className="w-full py-3 bg-celo-green hover:bg-green-500 text-white font-bold rounded-xl transition-all"
              >
                {t('Done')}
              </button>
            </div>
          )}

          {/* Failed / Rejected */}
          {(signingStep === 'failed' || signingStep === 'rejected') && (
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
                <XCircle className="w-10 h-10 text-red-600 dark:text-red-400" />
              </div>
              <div className="text-center">
                <p className="font-bold text-red-700 dark:text-red-400">
                  {signingStep === 'rejected' ? t('Transaction Rejected') : t('Transfer Failed')}
                </p>
                {error && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-xs">
                    {error}
                  </p>
                )}
              </div>
              <div className="flex gap-3 w-full">
                <button
                  onClick={onRetryWithTEE}
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition-all flex items-center justify-center gap-2"
                >
                  <Shield className="w-4 h-4" />
                  {t('Use Agent Wallet')}
                </button>
                <button
                  onClick={onClose}
                  className="flex-1 py-3 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 font-bold rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-all"
                >
                  {t('Cancel')}
                </button>
              </div>
            </div>
          )}

          {/* Preparing */}
          {signingStep === 'preparing' && (
            <div className="flex flex-col items-center gap-4 py-4">
              <Loader2 className="w-12 h-12 text-celo-green animate-spin" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t('Preparing transaction details...')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
