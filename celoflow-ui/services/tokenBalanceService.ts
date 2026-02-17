/**
 * Token Balance Service for CeloFlow
 *
 * Service layer for portfolio aggregation, USD value calculations,
 * and balance management with caching and analytics.
 */

import { TokenBalance, TokenPortfolio, PortfolioSummary } from '../types'
import { TOKEN_REGISTRY, getPriorityTokens, isStablecoin } from '../lib/token-registry'

// Mock price data - in production this would come from a price API
interface PriceData {
  [symbol: string]: {
    usd: number
    change24h: number
    lastUpdated: Date
  }
}

// Mock USD prices for tokens (would be fetched from price API in production)
const MOCK_PRICE_DATA: PriceData = {
  'CELO': { usd: 0.85, change24h: 2.5, lastUpdated: new Date() },
  'USDm': { usd: 1.00, change24h: 0.01, lastUpdated: new Date() },
  'EURm': { usd: 1.08, change24h: -0.2, lastUpdated: new Date() },
  'BRLm': { usd: 0.20, change24h: 0.5, lastUpdated: new Date() },
  'USDC': { usd: 1.00, change24h: 0.0, lastUpdated: new Date() },
  'USDT': { usd: 1.00, change24h: 0.02, lastUpdated: new Date() },
  'cUSD': { usd: 1.00, change24h: 0.01, lastUpdated: new Date() },
  'cEUR': { usd: 1.08, change24h: -0.1, lastUpdated: new Date() },
  // Add mock prices for other tokens as needed
  'XOFm': { usd: 0.0016, change24h: 0.0, lastUpdated: new Date() },
  'KESm': { usd: 0.0081, change24h: 0.1, lastUpdated: new Date() },
  'PHPm': { usd: 0.018, change24h: -0.05, lastUpdated: new Date() },
  'COPm': { usd: 0.00027, change24h: 0.2, lastUpdated: new Date() },
  'GBPm': { usd: 1.27, change24h: -0.3, lastUpdated: new Date() },
  'CADm': { usd: 0.74, change24h: 0.1, lastUpdated: new Date() },
  'AUDm': { usd: 0.66, change24h: 0.4, lastUpdated: new Date() },
  'ZARm': { usd: 0.053, change24h: -0.1, lastUpdated: new Date() },
  'GHSm': { usd: 0.083, change24h: 0.0, lastUpdated: new Date() },
  'NGNm': { usd: 0.00067, change24h: 0.3, lastUpdated: new Date() },
  'JPYm': { usd: 0.0067, change24h: -0.2, lastUpdated: new Date() },
  'CHFm': { usd: 1.12, change24h: 0.1, lastUpdated: new Date() },
  'vEUR': { usd: 1.08, change24h: -0.1, lastUpdated: new Date() },
  'vGBP': { usd: 1.27, change24h: -0.2, lastUpdated: new Date() },
  'vCHF': { usd: 1.12, change24h: 0.0, lastUpdated: new Date() },
  'USDM': { usd: 1.00, change24h: 0.5, lastUpdated: new Date() },
  'USDA': { usd: 1.00, change24h: 0.3, lastUpdated: new Date() },
  'EURA': { usd: 1.08, change24h: 0.2, lastUpdated: new Date() },
  'USDGLO': { usd: 1.00, change24h: 0.0, lastUpdated: new Date() },
  'BRLA': { usd: 0.20, change24h: 0.1, lastUpdated: new Date() },
  'COPM': { usd: 0.00027, change24h: 0.0, lastUpdated: new Date() },
  'G$': { usd: 0.001, change24h: 0.0, lastUpdated: new Date() }
}

export class TokenBalanceService {
  private priceCache: PriceData = { ...MOCK_PRICE_DATA }
  private lastPriceUpdate = new Date()
  private readonly PRICE_CACHE_TTL = 60000 // 1 minute

  /**
   * Calculate USD value for a token balance
   */
  calculateUSDValue(tokenBalance: TokenBalance): number {
    const price = this.getPrice(tokenBalance.symbol)
    const balanceInTokens = Number(tokenBalance.balance) / (10 ** tokenBalance.decimals)
    return balanceInTokens * price.usd
  }

  /**
   * Get price data for a token
   */
  getPrice(symbol: string): PriceData[string] {
    this.updatePriceCacheIfNeeded()
    
    if (!this.priceCache[symbol]) {
      // Default to $1 for stablecoins if no price data
      if (isStablecoin(symbol)) {
        return { usd: 1.00, change24h: 0.0, lastUpdated: new Date() }
      }
      
      // Return zero for unknown tokens
      return { usd: 0, change24h: 0.0, lastUpdated: new Date() }
    }
    
    return this.priceCache[symbol]
  }

  /**
   * Update price cache if needed (mock implementation)
   */
  private updatePriceCacheIfNeeded(): void {
    const now = new Date()
    if (now.getTime() - this.lastPriceUpdate.getTime() > this.PRICE_CACHE_TTL) {
      // In production, this would fetch from a price API
      // For now, just update the timestamp
      this.lastPriceUpdate = now
    }
  }

  /**
   * Enrich token balances with USD values and price data
   */
  enrichTokenBalances(balances: TokenBalance[]): TokenBalance[] {
    return balances.map(balance => {
      const priceData = this.getPrice(balance.symbol)
      const usdValue = this.calculateUSDValue(balance)
      
      return {
        ...balance,
        usdValue,
        change24h: priceData.change24h,
        lastUpdated: new Date()
      }
    })
  }

  /**
   * Calculate portfolio summary from token balances
   */
  calculatePortfolioSummary(balances: TokenBalance[]): PortfolioSummary {
    const nonZeroBalances = balances.filter(b => b.balance > 0n)
    
    const totalValueUsd = nonZeroBalances.reduce((sum, token) => 
      sum + (token.usdValue || 0), 0
    )
    
    const totalValueChange24h = nonZeroBalances.reduce((sum, token) => {
      const usdValue = token.usdValue || 0
      const change24h = token.change24h || 0
      return sum + (usdValue * (change24h / 100))
    }, 0)
    
    const totalValueChangePercent24h = totalValueUsd > 0 
      ? (totalValueChange24h / totalValueUsd) * 100 
      : 0

    return {
      totalValueUsd,
      totalValueChange24h,
      totalValueChangePercent24h,
      tokenCount: nonZeroBalances.length,
      hasZeroBalanceTokens: balances.some(b => b.balance === 0n),
      networkName: 'Celo' // Would be dynamic based on chain
    }
  }

  /**
   * Sort tokens by priority and balance
   */
  sortTokens(balances: TokenBalance[]): TokenBalance[] {
    const prioritySymbols = getPriorityTokens()
    
    return [...balances].sort((a, b) => {
      // First sort by priority (native token first, then priority tokens)
      const aPriority = a.symbol === 'CELO' ? -1 : prioritySymbols.indexOf(a.symbol)
      const bPriority = b.symbol === 'CELO' ? -1 : prioritySymbols.indexOf(b.symbol)
      
      if (aPriority !== bPriority) {
        const aPriorityValue = aPriority === -1 ? -1 : (aPriority === -1 ? 999 : aPriority)
        const bPriorityValue = bPriority === -1 ? -1 : (bPriority === -1 ? 999 : bPriority)
        return aPriorityValue - bPriorityValue
      }
      
      // Then sort by USD value (highest first)
      const aValue = a.usdValue || 0
      const bValue = b.usdValue || 0
      return bValue - aValue
    })
  }

  /**
   * Filter tokens by various criteria
   */
  filterTokens(
    balances: TokenBalance[], 
    filters: {
      minBalance?: string
      categories?: string[]
      searchQuery?: string
      includeZeroBalances?: boolean
    } = {}
  ): TokenBalance[] {
    let filtered = [...balances]
    
    // Filter by minimum balance
    if (filters.minBalance) {
      const minBalance = BigInt(filters.minBalance)
      filtered = filtered.filter(token => token.balance >= minBalance)
    }
    
    // Filter by categories
    if (filters.categories && filters.categories.length > 0) {
      filtered = filtered.filter(token => 
        filters.categories!.includes(token.category)
      )
    }
    
    // Filter by search query
    if (filters.searchQuery) {
      const query = filters.searchQuery.toLowerCase()
      filtered = filtered.filter(token =>
        token.symbol.toLowerCase().includes(query) ||
        token.name.toLowerCase().includes(query)
      )
    }
    
    // Filter zero balances
    if (!filters.includeZeroBalances) {
      filtered = filtered.filter(token => token.balance > 0n)
    }
    
    return filtered
  }

  /**
   * Get token balance changes over time
   */
  getBalanceChanges(
    currentBalances: TokenBalance[],
    previousBalances: TokenBalance[]
  ): Array<{ token: TokenBalance; change: number; changePercent: number }> {
    return currentBalances.map(current => {
      const previous = previousBalances.find(p => p.symbol === current.symbol)
      
      if (!previous || previous.balance === 0n) {
        return {
          token: current,
          change: Number(current.balance),
          changePercent: 0
        }
      }
      
      const change = Number(current.balance - previous.balance)
      const changePercent = (Number(change) / Number(previous.balance)) * 100
      
      return { token: current, change, changePercent }
    })
  }

  /**
   * Detect significant balance changes for notifications
   */
  detectSignificantChanges(
    currentBalances: TokenBalance[],
    previousBalances: TokenBalance[],
    thresholdPercent: number = 10
  ): TokenBalance[] {
    const changes = this.getBalanceChanges(currentBalances, previousBalances)
    
    return changes
      .filter(({ changePercent }) => Math.abs(changePercent) >= thresholdPercent)
      .map(({ token }) => token)
  }

  /**
   * Get portfolio analytics
   */
  getPortfolioAnalytics(balances: TokenBalance[]): {
    totalTokens: number
    tokensWithBalance: number
    largestHolding: TokenBalance | null
    smallestHolding: TokenBalance | null
    averageHoldingValue: number
    categoryBreakdown: Array<{ category: string; count: number; totalValue: number; percentage: number }>
  } {
    const tokensWithBalance = balances.filter(b => b.balance > 0n && b.usdValue && b.usdValue > 0)
    const totalValue = tokensWithBalance.reduce((sum, token) => sum + (token.usdValue || 0), 0)
    
    const categoryBreakdown = tokensWithBalance.reduce((acc, token) => {
      const category = token.category
      if (!acc[category]) {
        acc[category] = { count: 0, totalValue: 0 }
      }
      acc[category].count++
      acc[category].totalValue += token.usdValue || 0
      return acc
    }, {} as Record<string, { count: number; totalValue: number }>)

    const categoryBreakdownArray = Object.entries(categoryBreakdown).map(([category, data]) => ({
      category,
      count: data.count,
      totalValue: data.totalValue,
      percentage: totalValue > 0 ? (data.totalValue / totalValue) * 100 : 0
    }))

    const sortedByValue = tokensWithBalance.sort((a, b) => (b.usdValue || 0) - (a.usdValue || 0))
    
    return {
      totalTokens: balances.length,
      tokensWithBalance: tokensWithBalance.length,
      largestHolding: sortedByValue[0] || null,
      smallestHolding: sortedByValue[sortedByValue.length - 1] || null,
      averageHoldingValue: tokensWithBalance.length > 0 ? totalValue / tokensWithBalance.length : 0,
      categoryBreakdown: categoryBreakdownArray.sort((a, b) => b.totalValue - a.totalValue)
    }
  }

  /**
   * Format balance for display
   */
  formatBalance(balance: TokenBalance, options: {
    showSymbol?: boolean
    showUSDValue?: boolean
    maxDecimals?: number
  } = {}): string {
    const { showSymbol = true, showUSDValue = false, maxDecimals = 4 } = options
    
    let formatted = balance.formattedBalance
    
    // Limit decimal places
    if (maxDecimals < balance.formattedBalance.split('.')[1]?.length) {
      const parts = balance.formattedBalance.split('.')
      formatted = `${parts[0]}.${parts[1].slice(0, maxDecimals)}`
    }
    
    if (showSymbol) {
      formatted += ` ${balance.symbol}`
    }
    
    if (showUSDValue && balance.usdValue) {
      const usdFormatted = balance.usdValue.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
      formatted += ` (${usdFormatted})`
    }
    
    return formatted
  }

  /**
   * Clear price cache
   */
  clearPriceCache(): void {
    this.priceCache = { ...MOCK_PRICE_DATA }
    this.lastPriceUpdate = new Date()
  }
}

// Export singleton instance
export const tokenBalanceService = new TokenBalanceService()
