/**
 * Token Portfolio Component for CeloFlow
 *
 * Displays comprehensive multi-token portfolio with expandable details,
 * balance information, and portfolio analytics.
 */

import React, { useState } from 'react'
import { 
  ChevronDown, 
  ChevronUp, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  DollarSign,
  Copy,
  Check,
  Settings
} from 'lucide-react'
import { TokenBalance, PortfolioSummary } from '../types'
import { tokenBalanceService } from '../services/tokenBalanceService'
import { useI18n } from '../lib/language'

interface TokenPortfolioProps {
  portfolio: {
    tokens: TokenBalance[]
    totalValueUsd: number
    totalValueChange24h: number
    lastUpdated: Date
    isLoading: boolean
    error?: string
  }
  summary: PortfolioSummary
  refreshState: {
    isRefreshing: boolean
    lastRefreshTime: Date
    refreshError?: string
    autoRefreshEnabled: boolean
  }
  onRefresh: () => void
  onToggleAutoRefresh: () => void
  compact?: boolean
}

export const TokenPortfolio: React.FC<TokenPortfolioProps> = ({
  portfolio,
  summary,
  refreshState,
  onRefresh,
  onToggleAutoRefresh,
  compact = false
}) => {
  const { t } = useI18n()
  const [isExpanded, setIsExpanded] = useState(false)
  const [copiedToken, setCopiedToken] = useState<string | null>(null)

  // Sort tokens using the service
  const sortedTokens = tokenBalanceService.sortTokens(portfolio.tokens)

  // Filter tokens with non-zero balance for display
  const displayTokens = sortedTokens.filter(token => token.balance > 0n)

  const handleCopyAddress = async (address: string, tokenSymbol: string) => {
    await navigator.clipboard.writeText(address)
    setCopiedToken(tokenSymbol)
    setTimeout(() => setCopiedToken(null), 2000)
  }

  const formatLastUpdated = (date: Date) => {
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return t('Just now')
    if (diffMins < 60) return `${diffMins} ${t('minutes ago')}`
    
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours} ${t('hours ago')}`
    
    return date.toLocaleDateString()
  }

  const getTokenIcon = (symbol: string) => {
    // In production, these would be actual token logos
    const iconColors: Record<string, string> = {
      'CELO': 'bg-green-500',
      'USDm': 'bg-blue-500',
      'USDC': 'bg-blue-600',
      'USDT': 'bg-green-600',
      'EURm': 'bg-yellow-500',
      'default': 'bg-gray-500'
    }
    
    return iconColors[symbol] || iconColors.default
  }

  if (compact) {
    return (
      <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
              {t('Portfolio Value')}
            </div>
            <div className="text-lg font-bold text-gray-900 dark:text-white">
              ${summary.totalValueUsd.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </div>
            {summary.totalValueChangePercent24h !== 0 && (
              <div className={`text-xs flex items-center gap-1 ${
                summary.totalValueChangePercent24h >= 0 
                  ? 'text-green-600 dark:text-green-400' 
                  : 'text-red-600 dark:text-red-400'
              }`}>
                {summary.totalValueChangePercent24h >= 0 ? (
                  <TrendingUp className="w-3 h-3" />
                ) : (
                  <TrendingDown className="w-3 h-3" />
                )}
                {Math.abs(summary.totalValueChangePercent24h).toFixed(2)}%
              </div>
            )}
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {summary.tokenCount} {t('tokens')}
            </div>
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-1 text-xs text-celo-green hover:text-green-600 flex items-center gap-1"
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="w-3 h-3" />
                  {t('Hide')}
                </>
              ) : (
                <>
                  <ChevronDown className="w-3 h-3" />
                  {t('Show')}
                </>
              )}
            </button>
          </div>
        </div>

        {isExpanded && displayTokens.length > 0 && (
          <div className="mt-3 space-y-2 border-t border-gray-100 dark:border-gray-700 pt-3">
            {displayTokens.slice(0, 3).map(token => (
              <div key={token.symbol} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className={`w-4 h-4 rounded-full ${getTokenIcon(token.symbol)}`} />
                  <span className="text-gray-900 dark:text-white">{token.symbol}</span>
                </div>
                <span className="text-gray-600 dark:text-gray-400">
                  {tokenBalanceService.formatBalance(token, { showSymbol: false })}
                </span>
              </div>
            ))}
            {displayTokens.length > 3 && (
              <div className="text-xs text-gray-500 dark:text-gray-400 text-center">
                +{displayTokens.length - 3} {t('more tokens')}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="p-4">
      {/* Portfolio Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
            {t('Token Portfolio')}
          </h3>
          <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
            <span>{summary.tokenCount} {t('tokens')}</span>
            <span>{formatLastUpdated(portfolio.lastUpdated)}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleAutoRefresh}
            className={`p-2 rounded-lg transition-colors ${
              refreshState.autoRefreshEnabled
                ? 'bg-celo-green text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
            title={refreshState.autoRefreshEnabled ? t('Auto-refresh enabled') : t('Auto-refresh disabled')}
          >
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={onRefresh}
            disabled={refreshState.isRefreshing}
            className="p-2 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
            title={t('Refresh balances')}
          >
            <RefreshCw className={`w-4 h-4 ${refreshState.isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Portfolio Summary */}
      <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              {t('Total Value')}
            </div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              ${summary.totalValueUsd.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              {t('24h Change')}
            </div>
            <div className={`text-2xl font-bold flex items-center gap-2 ${
              summary.totalValueChange24h >= 0 
                ? 'text-green-600 dark:text-green-400' 
                : 'text-red-600 dark:text-red-400'
            }`}>
              {summary.totalValueChange24h >= 0 ? (
                <TrendingUp className="w-5 h-5" />
              ) : (
                <TrendingDown className="w-5 h-5" />
              )}
              ${Math.abs(summary.totalValueChange24h).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
              })}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
              {t('24h Change %')}
            </div>
            <div className={`text-2xl font-bold ${
              summary.totalValueChangePercent24h >= 0 
                ? 'text-green-600 dark:text-green-400' 
                : 'text-red-600 dark:text-red-400'
            }`}>
              {summary.totalValueChangePercent24h >= 0 ? '+' : ''}
              {summary.totalValueChangePercent24h.toFixed(2)}%
            </div>
          </div>
        </div>
      </div>

      {/* Error Display */}
      {(portfolio.error || refreshState.refreshError) && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
          <div className="text-sm text-red-600 dark:text-red-400">
            {portfolio.error || refreshState.refreshError}
          </div>
        </div>
      )}

      {/* Loading State */}
      {portfolio.isLoading && (
        <div className="text-center py-8">
          <RefreshCw className="w-6 h-6 animate-spin text-celo-green mx-auto mb-2" />
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {t('Loading balances...')}
          </div>
        </div>
      )}

      {/* Token List */}
      {!portfolio.isLoading && displayTokens.length === 0 && (
        <div className="text-center py-8">
          <DollarSign className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <div className="text-gray-600 dark:text-gray-400 mb-2">
            {t('No tokens found')}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-500 mb-4">
            {t('Your token balances will appear here')}
          </div>
          
          {/* Debug Information */}
          <div className="text-xs text-gray-400 dark:text-gray-600 bg-gray-50 dark:bg-gray-800 rounded-lg p-3 max-w-sm mx-auto">
            <div className="text-left space-y-1">
              <div><strong>Debug Info:</strong></div>
              <div>Total tokens queried: {portfolio.tokens.length}</div>
              <div>Loading: {portfolio.isLoading ? 'Yes' : 'No'}</div>
              <div>Network: {summary.networkName}</div>
              {portfolio.error && <div className="text-red-500">Error: {portfolio.error}</div>}
              <div className="mt-2 text-gray-500">
                If you have tokens, they may take a moment to load. Try refreshing.
              </div>
            </div>
          </div>
        </div>
      )}

      {!portfolio.isLoading && displayTokens.length > 0 && (
        <div className="space-y-2">
          {displayTokens.map(token => (
            <div
              key={token.symbol}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full ${getTokenIcon(token.symbol)} flex items-center justify-center`}>
                    <span className="text-white text-xs font-bold">
                      {token.symbol.slice(0, 2)}
                    </span>
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white">
                      {token.name}
                    </div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      {token.symbol} • {token.category}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-medium text-gray-900 dark:text-white">
                    {tokenBalanceService.formatBalance(token, { showSymbol: false })}
                  </div>
                  {token.usdValue && (
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      ${token.usdValue.toLocaleString('en-US', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                      })}
                    </div>
                  )}
                  {token.change24h && (
                    <div className={`text-xs flex items-center gap-1 justify-end ${
                      token.change24h >= 0 
                        ? 'text-green-600 dark:text-green-400' 
                        : 'text-red-600 dark:text-red-400'
                    }`}>
                      {token.change24h >= 0 ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      {Math.abs(token.change24h).toFixed(2)}%
                    </div>
                  )}
                </div>
              </div>
              
              {/* Token Actions */}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {t('Contract')}: {token.contractAddress.slice(0, 8)}…{token.contractAddress.slice(-6)}
                </div>
                <button
                  onClick={() => handleCopyAddress(token.contractAddress, token.symbol)}
                  className="text-xs text-celo-green hover:text-green-600 flex items-center gap-1"
                >
                  {copiedToken === token.symbol ? (
                    <>
                      <Check className="w-3 h-3" />
                      {t('Copied!')}
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      {t('Copy')}
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Analytics Summary */}
      {!portfolio.isLoading && displayTokens.length > 0 && (
        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {displayTokens.length}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {t('Active Tokens')}
              </div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {displayTokens.filter(t => isStablecoin(t.symbol)).length}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {t('Stablecoins')}
              </div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {displayTokens.filter(t => t.category === 'mento').length}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {t('Mento Tokens')}
              </div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {summary.networkName}
              </div>
              <div className="text-xs text-gray-600 dark:text-gray-400">
                {t('Network')}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Helper function to check if token is stablecoin
function isStablecoin(symbol: string): boolean {
  return symbol !== 'CELO'
}
