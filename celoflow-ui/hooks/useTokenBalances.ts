/**
 * Multi-Token Balance Hook for CeloFlow - Working Version
 *
 * Custom hook for fetching and managing balances across multiple tokens
 * using wagmi's useBalance hook with proper React hook rules.
 */

import { useAccount, useBalance, useReadContract } from 'wagmi'
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
import { tokenBalanceService } from '../services/tokenBalanceService'
import { parseAbi } from 'viem'

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

  // Get tokens to query based on options
  const tokensToQuery = useMemo(() => {
    let chainId = chain?.id
    
    // If no chain ID but wallet is connected, try to detect from connected wallet
    if (!chainId && isConnected && address) {
      console.log('[useTokenBalances] No chain ID from wagmi, trying fallback detection')
      
      // Use custom chain ID from environment variables if available
      const customChainId = import.meta.env.VITE_CELO_CHAIN_ID
      if (customChainId) {
        chainId = parseInt(customChainId)
        console.log('[useTokenBalances] Using custom chain ID from env:', chainId)
      } else {
        chainId = 42220 // Default to Celo Mainnet
        console.log('[useTokenBalances] Using fallback chain ID:', chainId)
      }
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

  // Get native CELO balance separately (working version)
  // Use custom chain ID from environment variables if available
  const customChainId = import.meta.env.VITE_CELO_CHAIN_ID
  const balanceChainId = chain?.id || (customChainId ? parseInt(customChainId) : 42220)
  
  const { data: nativeBalanceData, isLoading: isNativeLoading, error: nativeError } = useBalance({
    address: address as `0x${string}`,
    chainId: balanceChainId
  })

  // ERC-20 ABI for balanceOf function
  const erc20Abi = parseAbi([
    'function balanceOf(address account) view returns (uint256)',
    'function decimals() view returns (uint8)',
    'function symbol() view returns (string)',
    'function name() view returns (string)'
  ])

  // Get key ERC-20 token balances using useReadContract (React Rules of Hooks compliant)
  const { data: usdcBalanceData, isLoading: isUSDCLoading, error: usdcError } = useReadContract({
    address: '0xceba9300f2b948710d2653dd7b07f33a8b32118c' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  })

  const { data: usdtBalanceData, isLoading: isUSDTLoading, error: usdtError } = useReadContract({
    address: '0x48065fbbe25f71c9282ddf5e1cd6d6a887483d5e' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  })

  const { data: usdmBalanceData, isLoading: isUSDMLoading, error: usdmError } = useReadContract({
    address: '0x765de816845861e75a25fca122bb6898b8b1282a' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  })

  const { data: eurmbalanceData, isLoading: isEURMLoading, error: eurError } = useReadContract({
    address: '0x10a89a440b0c943d2aa7c2a75ef3445e6b3a1e4b' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  })

  const { data: brlmbalanceData, isLoading: isBRLMLoading, error: brlmError } = useReadContract({
    address: '0x874069fa1eb16d44d6aF880e83451f1e28d31477' as `0x${string}`,
    abi: erc20Abi,
    functionName: 'balanceOf',
    args: [address as `0x${string}`],
    chainId: balanceChainId,
    query: { enabled: isConnected && !!address }
  })

  // Process balance data into TokenBalance objects
  const tokenBalances = useMemo(() => {
    console.log(`[useTokenBalances] Processing balances for ${tokensToQuery.length} tokens`)
    
    let chainId = chain?.id
    if (!chainId && isConnected && address) {
      chainId = 42220 // Fallback to Celo Mainnet
    }

    const balances: TokenBalance[] = []

    // Add native CELO balance
    if (nativeBalanceData) {
      const token = TOKEN_REGISTRY.CELO
      const balance = nativeBalanceData.value
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] CELO balance: ${formattedBalance}`)
      
      balances.push({
        symbol: token.symbol,
        name: token.name,
        balance,
        decimals: token.decimals,
        formattedBalance,
        contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
        category: token.category,
        isNative: token.category === 'native',
        lastUpdated: new Date()
      })
    }

    // Add USDC balance
    if (usdcBalanceData !== undefined) {
      const token = TOKEN_REGISTRY.USDC
      const balance = usdcBalanceData as bigint
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] USDC balance: ${formattedBalance}`)
      
      if (includeZeroBalances || balance > 0n) {
        balances.push({
          symbol: token.symbol,
          name: token.name,
          balance,
          decimals: token.decimals,
          formattedBalance,
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date()
        })
      }
    }

    // Add USDT balance
    if (usdtBalanceData !== undefined) {
      const token = TOKEN_REGISTRY.USDT
      const balance = usdtBalanceData as bigint
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] USDT balance: ${formattedBalance}`)
      
      if (includeZeroBalances || balance > 0n) {
        balances.push({
          symbol: token.symbol,
          name: token.name,
          balance,
          decimals: token.decimals,
          formattedBalance,
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date()
        })
      }
    }

    // Add USDm balance
    if (usdmBalanceData !== undefined) {
      const token = TOKEN_REGISTRY.USDm
      const balance = usdmBalanceData as bigint
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] USDm balance: ${formattedBalance}`)
      
      if (includeZeroBalances || balance > 0n) {
        balances.push({
          symbol: token.symbol,
          name: token.name,
          balance,
          decimals: token.decimals,
          formattedBalance,
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date()
        })
      }
    }

    // Add EURm balance
    if (eurmbalanceData !== undefined) {
      const token = TOKEN_REGISTRY.EURm
      const balance = eurmbalanceData as bigint
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] EURm balance: ${formattedBalance}`)
      
      if (includeZeroBalances || balance > 0n) {
        balances.push({
          symbol: token.symbol,
          name: token.name,
          balance,
          decimals: token.decimals,
          formattedBalance,
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date()
        })
      }
    }

    // Add BRLm balance
    if (brlmbalanceData !== undefined) {
      const token = TOKEN_REGISTRY.BRLm
      const balance = brlmbalanceData as bigint
      const formattedBalance = formatBalance(balance, token.decimals)
      
      console.log(`[useTokenBalances] BRLm balance: ${formattedBalance}`)
      
      if (includeZeroBalances || balance > 0n) {
        balances.push({
          symbol: token.symbol,
          name: token.name,
          balance,
          decimals: token.decimals,
          formattedBalance,
          contractAddress: getTokenContractAddress(token.symbol, chainId || 42220),
          category: token.category,
          isNative: token.category === 'native',
          lastUpdated: new Date()
        })
      }
    }

    // Enrich with USD values using the service
    const enrichedBalances = tokenBalanceService.enrichTokenBalances(balances)
    const sortedBalances = tokenBalanceService.sortTokens(enrichedBalances)
    
    console.log(`[useTokenBalances] Final processed tokens: ${sortedBalances.length}`)
    sortedBalances.forEach(token => {
      console.log(`[useTokenBalances] Final token: ${token.symbol} = ${token.formattedBalance}`)
    })
    
    return sortedBalances
  }, [
    tokensToQuery, 
    chain?.id, 
    includeZeroBalances, 
    isConnected, 
    address,
    nativeBalanceData
  ])

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
      isLoading: isNativeLoading || isUSDCLoading || isUSDTLoading || isUSDMLoading || isEURMLoading || isBRLMLoading,
      error: hasError ? errorMessages : undefined
    }
  }, [tokenBalances, address, chain?.id, isNativeLoading, isUSDCLoading, isUSDTLoading, isUSDMLoading, isEURMLoading, isBRLMLoading])

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
