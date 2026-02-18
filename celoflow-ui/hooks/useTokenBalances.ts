/**
 * Multi-Token Balance Hook for CeloFlow - Dynamic Multicall Version
 *
 * Custom hook for fetching and managing balances across ALL tokens
 * in the registry using wagmi's useReadContracts (multicall) for
 * efficient batch querying. Replaces hardcoded per-token calls.
 */

import { useAccount, useBalance, useReadContracts } from 'wagmi'
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
  isStablecoin,
  type TokenInfo
} from '../lib/token-registry'
import { tokenBalanceService } from '../services/tokenBalanceService'
import { erc20Abi } from 'viem'

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
 * Custom hook for fetching multi-token balances
 */
export function useTokenBalances(options: UseTokenBalancesOptions = {}): UseTokenBalancesReturn {
  const { 
    includeZeroBalances = false,
    priorityTokensOnly = false,
    refreshInterval = 30000,
    autoRefresh = true
  } = options

  const { address, chain, isConnected } = useAccount()
  const [refreshState, setRefreshState] = useState<BalanceRefreshState>({
    isRefreshing: false,
    lastRefreshTime: new Date(),
    refreshError: undefined,
    autoRefreshEnabled: autoRefresh
  })

  // Resolve chain ID with fallback
  const customChainId = import.meta.env.VITE_CELO_CHAIN_ID
  const resolvedChainId = chain?.id || (customChainId ? parseInt(customChainId) : 42220)

  // Get ERC-20 tokens to query based on options (excludes native CELO)
  const erc20Tokens = useMemo(() => {
    let chainId = chain?.id
    
    if (!chainId && isConnected && address) {
      chainId = customChainId ? parseInt(customChainId) : 42220
    }
    
    if (!chainId) return []
    
    const availableTokens = getTokensForNetwork(chainId)
    const nonNative = availableTokens.filter(t => t.category !== 'native')
    
    if (priorityTokensOnly) {
      const prioritySymbols = getPriorityTokens()
      return nonNative.filter(token => prioritySymbols.includes(token.symbol))
    }
    
    return nonNative
  }, [chain?.id, priorityTokensOnly, isConnected, address, customChainId])

  // Get native CELO balance
  const { data: nativeBalanceData, isLoading: isNativeLoading } = useBalance({
    address: address as `0x${string}`,
    chainId: resolvedChainId
  })

  // Build multicall contracts array for all ERC-20 tokens
  const contracts = useMemo(() => {
    if (!isConnected || !address) return []
    
    return erc20Tokens.map(token => {
      let tokenAddress: string
      try {
        tokenAddress = getTokenContractAddress(token.symbol, resolvedChainId)
      } catch {
        return null
      }
      if (tokenAddress === '0x0000000000000000000000000000000000000000') return null
      
      return {
        address: tokenAddress as `0x${string}`,
        abi: erc20Abi,
        functionName: 'balanceOf' as const,
        args: [address as `0x${string}`],
        chainId: resolvedChainId,
      }
    }).filter((c): c is NonNullable<typeof c> => c !== null)
  }, [erc20Tokens, address, isConnected, resolvedChainId])

  // Single multicall for ALL ERC-20 token balances
  const { data: multicallResults, isLoading: isMulticallLoading } = useReadContracts({
    contracts,
    query: { enabled: isConnected && !!address && contracts.length > 0 }
  })

  // Process balance data into TokenBalance objects
  const tokenBalances = useMemo(() => {
    let chainId = chain?.id
    if (!chainId && isConnected && address) {
      chainId = resolvedChainId
    }

    const balances: TokenBalance[] = []

    // Add native CELO balance
    if (nativeBalanceData) {
      const token = TOKEN_REGISTRY.CELO
      const balance = nativeBalanceData.value
      const formattedBalance = formatBalance(balance, token.decimals)
      
      balances.push({
        symbol: token.symbol,
        name: token.name,
        balance,
        decimals: token.decimals,
        formattedBalance,
        contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
        category: token.category,
        isNative: true,
        lastUpdated: new Date()
      })
    }

    // Process multicall results — map each result back to its token
    if (multicallResults) {
      // Build a filtered token list matching the contracts array
      const filteredTokens: TokenInfo[] = []
      for (const token of erc20Tokens) {
        try {
          const addr = getTokenContractAddress(token.symbol, resolvedChainId)
          if (addr !== '0x0000000000000000000000000000000000000000') {
            filteredTokens.push(token)
          }
        } catch {
          // skip
        }
      }

      for (let i = 0; i < multicallResults.length; i++) {
        const result = multicallResults[i]
        const token = filteredTokens[i]
        if (!token) continue

        if (result.status === 'success' && result.result !== undefined) {
          const balance = result.result as bigint
          if (!includeZeroBalances && balance === 0n) continue

          const formattedBalance = formatBalance(balance, token.decimals)
          let contractAddr: string
          try {
            contractAddr = getTokenContractAddress(token.symbol, chainId || 42220)
          } catch {
            contractAddr = '0x0000000000000000000000000000000000000000'
          }

          balances.push({
            symbol: token.symbol,
            name: token.name,
            balance,
            decimals: token.decimals,
            formattedBalance,
            contractAddress: contractAddr,
            category: token.category,
            isNative: false,
            lastUpdated: new Date()
          })
        }
      }
    }

    // Enrich with USD values using the service
    const enrichedBalances = tokenBalanceService.enrichTokenBalances(balances)
    return tokenBalanceService.sortTokens(enrichedBalances)
  }, [
    erc20Tokens,
    chain?.id, 
    includeZeroBalances, 
    isConnected, 
    address,
    nativeBalanceData,
    multicallResults,
    resolvedChainId,
  ])

  // Calculate portfolio
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
      isLoading: isNativeLoading || isMulticallLoading,
      error: hasError ? errorMessages : undefined
    }
  }, [tokenBalances, address, chain?.id, isNativeLoading, isMulticallLoading])

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

  // Auto-refresh effect
  useEffect(() => {
    if (!refreshState.autoRefreshEnabled || !isConnected) return

    const interval = setInterval(() => {
      refreshBalances()
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [refreshState.autoRefreshEnabled, refreshInterval, isConnected, refreshBalances])

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

    // For native tokens, use address as undefined
    // For ERC-20 tokens, we need to use the correct wagmi v3 API
    const tokenAddress = token.category === 'native' ? undefined : getTokenContractAddress(tokenSymbol, chain.id) as `0x${string}`

    // TODO: Fix ERC-20 token fetching with proper wagmi v3 API
    // For now, only support native tokens
    if (token.category !== 'native') {
      return {
        data: null,
        isLoading: false,
        error: 'ERC-20 token fetching not yet implemented'
      }
    }

    const balanceQuery = useBalance({
      address: address as `0x${string}`,
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
