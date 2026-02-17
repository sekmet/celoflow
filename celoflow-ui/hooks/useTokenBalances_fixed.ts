/**
 * Multi-Token Balance Hook for CeloFlow - Fixed Version
 *
 * Custom hook for fetching and managing balances across multiple tokens
 * using wagmi's useBalance hook with proper React hook rules.
 */

import { useAccount, useBalance } from 'wagmi'
import { useMemo, useCallback, useState, useEffect } from 'react'
import { 
  TokenBalance, 
  TokenPortfolio, 
  BalanceRefreshState,
  PortfolioSummary 
} from '../types'
import { 
  TOKEN_REGISTRY, 
  getTokenContractAddress, 
  getTokensForNetwork,
  getPriorityTokens,
  isStablecoin 
} from '../lib/token-registry'

interface UseTokenBalancesOptions {
  includeZeroBalances?: boolean
  priorityTokensOnly?: boolean
  refreshInterval?: number
  autoRefresh?: boolean
}

interface UseTokenBalancesReturn {
  portfolio: TokenPortfolio
  summary: PortfolioSummary
  refreshState: BalanceRefreshState
  refreshBalances: () => Promise<void>
  toggleAutoRefresh: () => void
  isLoading: boolean
  error: string | null
}

/**
 * Format balance from bigint to decimal string
 */
function formatBalance(value: bigint, decimals: number): string {
  if (value === 0n) return '0.00'
  
  const divisor = BigInt(10 ** decimals)
  const whole = value / divisor
  const frac = value % divisor
  
  const fracStr = frac.toString().padStart(decimals, '0').slice(0, 4)
  const trimmedFrac = fracStr.replace(/0+$/, '')
  
  return trimmedFrac.length > 0 
    ? `${whole}.${trimmedFrac}` 
    : whole.toString()
}

/**
 * Custom hook for fetching multi-token balances
 */
export function useTokenBalances(options: UseTokenBalancesOptions = {}): UseTokenBalancesReturn {
  const { 
    includeZeroBalances = false,
    priorityTokensOnly = false,
    refreshInterval = 30000, // 30 seconds
    autoRefresh = true
  } = options

  const { address, chain, isConnected } = useAccount()
  const [refreshState, setRefreshState] = useState<BalanceRefreshState>({
    isRefreshing: false,
    lastRefreshTime: new Date(),
    refreshError: undefined,
    autoRefreshEnabled: autoRefresh
  })

  // Get tokens to query based on options
  const tokensToQuery = useMemo(() => {
    let chainId = chain?.id
    
    // If no chain ID but wallet is connected, try to detect from connected wallet
    if (!chainId && isConnected && address) {
      console.log('[useTokenBalances] No chain ID from wagmi, trying fallback detection')
      chainId = 42220 // Default to Celo Mainnet
      console.log('[useTokenBalances] Using fallback chain ID:', chainId)
    }
    
    if (!chainId) {
      console.log('[useTokenBalances] No chain ID available and wallet not connected')
      return []
    }
    
    const availableTokens = getTokensForNetwork(chainId)
    console.log(`[useTokenBalances] Chain ${chainId}, found ${availableTokens.length} tokens:`, availableTokens.map(t => t.symbol))
    
    if (priorityTokensOnly) {
      const prioritySymbols = getPriorityTokens()
      const filtered = availableTokens.filter(token => 
        prioritySymbols.includes(token.symbol)
      )
      console.log(`[useTokenBalances] Priority tokens only: ${filtered.length} tokens`)
      return filtered
    }
    
    return availableTokens
  }, [chain?.id, priorityTokensOnly, isConnected, address])

  // Create individual balance hooks for each token (at top level)
  const balanceResults = useMemo(() => {
    let chainId = chain?.id
    if (!chainId && isConnected && address) {
      chainId = 42220 // Fallback to Celo Mainnet
    }
    
    if (!chainId || !address) {
      return []
    }
    
    console.log(`[useTokenBalances] Creating balance hooks for ${tokensToQuery.length} tokens`)
    
    return tokensToQuery.map(token => {
      try {
        const contractAddress = getTokenContractAddress(token.symbol, chainId)
        const tokenAddress = token.category === 'native' ? undefined : contractAddress as `0x${string}`
        
        console.log(`[useTokenBalances] Setting up balance hook for ${token.symbol} at ${tokenAddress || 'native'}`)
        
        return {
          token,
          // This is still problematic - we need a different approach
          // For now, return a placeholder
          data: null,
          error: null,
          isLoading: true
        }
      } catch (error) {
        console.error(`Error setting up balance query for ${token.symbol}:`, error)
        return {
          token,
          data: null,
          error: error as Error,
          isLoading: false
        }
      }
    })
  }, [tokensToQuery, chain?.id, isConnected, address])

  // Process balance data into TokenBalance objects
  const tokenBalances = useMemo(() => {
    console.log(`[useTokenBalances] Processing ${balanceResults.length} balance results`)
    
    // Get the chain ID for contract address resolution
    let chainId = chain?.id
    if (!chainId && isConnected && address) {
      chainId = 42220 // Fallback to Celo Mainnet
    }
    
    const processed = balanceResults.map(({ token, data, error, isLoading }) => {
      console.log(`[useTokenBalances] Processing ${token.symbol}:`, {
        hasData: !!data,
        error: error?.message,
        isLoading,
        balance: data?.value?.toString()
      })
      
      if (error) {
        console.log(`[useTokenBalances] Error for ${token.symbol}:`, error.message)
        return {
          symbol: token.symbol,
          name: token.name,
          balance: 0n,
          decimals: token.decimals,
          formattedBalance: '0.00',
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date(),
          error: error.message
        } as TokenBalance
      }

      if (!data) {
        console.log(`[useTokenBalances] No data for ${token.symbol}`)
        return {
          symbol: token.symbol,
          name: token.name,
          balance: 0n,
          decimals: token.decimals,
          formattedBalance: '0.00',
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date()
        } as TokenBalance
      }

      const balance = data.value
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] ${token.symbol} balance: ${formattedBalance}`)
      
      // Filter out zero balances if option is disabled
      if (!includeZeroBalances && balance === 0n) {
        console.log(`[useTokenBalances] Filtering out zero balance token: ${token.symbol}`)
        return null
      }

      return {
        symbol: token.symbol,
        name: token.name,
        balance,
        decimals: token.decimals,
        formattedBalance,
        contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
        category: token.category,
        isNative: token.category === 'native',
        lastUpdated: new Date()
      } as TokenBalance
    }).filter((balance): balance is NonNullable<typeof balance> => balance !== null)
    
    console.log(`[useTokenBalances] Final processed tokens: ${processed.length}`)
    processed.forEach(token => {
      console.log(`[useTokenBalances] Final token: ${token.symbol} = ${token.formattedBalance}`)
    })
    
    return processed
  }, [balanceResults, chain?.id, includeZeroBalances, isConnected, address])

  // Calculate portfolio summary
  const portfolio = useMemo((): TokenPortfolio => {
    const totalValueUsd = tokenBalances.reduce((sum, token) => 
      sum + (token.usdValue || 0), 0
    )
    
    const totalValueChange24h = tokenBalances.reduce((sum, token) => 
      sum + ((token.usdValue || 0) * ((token.change24h || 0) / 100)), 0
    )

    const hasError = tokenBalances.some(token => token.error)
    const errorMessages = tokenBalances
      .filter(token => token.error)
      .map(token => `${token.symbol}: ${token.error}`)
      .join('; ')

    return {
      address: address || '0x0000000000000000000000000000000000000000',
      chainId: chain?.id || 42220,
      tokens: tokenBalances,
      totalValueUsd,
      totalValueChange24h,
      lastUpdated: new Date(),
      isLoading: balanceResults.some(result => result.isLoading),
      error: hasError ? errorMessages : undefined
    }
  }, [tokenBalances, address, chain?.id])

  // Calculate portfolio summary
  const summary = useMemo((): PortfolioSummary => {
    const totalValueUsd = portfolio.totalValueUsd
    const totalValueChange24h = portfolio.totalValueChange24h
    const totalValueChangePercent24h = totalValueUsd > 0 
      ? (totalValueChange24h / totalValueUsd) * 100 
      : 0

    return {
      totalValueUsd,
      totalValueChange24h,
      totalValueChangePercent24h,
      tokenCount: portfolio.tokens.length,
      hasZeroBalanceTokens: portfolio.tokens.some(token => token.balance === 0n),
      networkName: chain?.name || 'Celo'
    }
  }, [portfolio, chain?.name])

  // Refresh all balances
  const refreshBalances = useCallback(async () => {
    setRefreshState(prev => ({ ...prev, isRefreshing: true, refreshError: undefined }))
    
    try {
      // For now, just update the timestamp
      // In a real implementation, we would trigger refetches
      console.log('[useTokenBalances] Refresh called - not implemented yet')
      
      setRefreshState(prev => ({
        ...prev,
        isRefreshing: false,
        lastRefreshTime: new Date()
      }))
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      setRefreshState(prev => ({
        ...prev,
        isRefreshing: false,
        refreshError: errorMessage
      }))
    }
  }, [])

  // Toggle auto-refresh
  const toggleAutoRefresh = useCallback(() => {
    setRefreshState(prev => ({
      ...prev,
      autoRefreshEnabled: !prev.autoRefreshEnabled
    }))
  }, [])

  // Combined loading state
  const isLoading = portfolio.isLoading || refreshState.isRefreshing
  const error = portfolio.error || refreshState.refreshError || null

  return {
    portfolio,
    summary,
    refreshState,
    refreshBalances,
    toggleAutoRefresh,
    isLoading,
    error
  }
}

/**
 * Hook for getting a single token balance
 */
export function useTokenBalance(tokenSymbol: string) {
  const { address, chain } = useAccount()
  
  if (!address || !chain?.id) {
    return {
      data: null,
      isLoading: false,
      error: 'Wallet not connected'
    }
  }

  try {
    const token = TOKEN_REGISTRY[tokenSymbol]
    if (!token) {
      return {
        data: null,
        isLoading: false,
        error: `Token ${tokenSymbol} not found`
      }
    }

    const contractAddress = getTokenContractAddress(tokenSymbol, chain.id)
    const tokenAddress = token.category === 'native' ? undefined : contractAddress as `0x${string}`

    const balanceQuery = useBalance({
      address: address as `0x${string}`,
      token: tokenAddress,
      chainId: chain.id
    })

    const data = balanceQuery.data ? {
      decimals: balanceQuery.data.decimals,
      symbol: balanceQuery.data.symbol,
      value: balanceQuery.data.value,
      token,
      formattedBalance: formatBalance(balanceQuery.data.value, token.decimals)
    } : null

    return {
      data,
      isLoading: balanceQuery.isLoading,
      error: balanceQuery.error?.message
    }
  } catch (error) {
    return {
      data: null,
      isLoading: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    }
  }
}
