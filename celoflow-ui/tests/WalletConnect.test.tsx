/**
 * Integration Tests for CeloFlow Multi-Coin Wallet Display
 *
 * Tests for WalletConnect component with multi-token support,
 * TokenPortfolio component, and balance services.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, test, expect, beforeEach, vi } from 'vitest'
import { WagmiProvider } from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { config } from '../lib/wagmi-config'
import { WalletConnect } from '../components/WalletConnect'
import { TokenPortfolio } from '../components/TokenPortfolio'
import { useTokenBalances } from '../hooks/useTokenBalances'
import { tokenBalanceService } from '../services/tokenBalanceService'
import { TOKEN_REGISTRY } from '../lib/token-registry'
import { celo, celoAlfajores } from 'wagmi/chains'
import { TokenBalance, PortfolioSummary } from '../types'

// Test wrapper with providers
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })

  return ({ children }: { children: React.ReactNode }) => (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </WagmiProvider>
  )
}

// Mock token balance data
const mockTokenBalances: TokenBalance[] = [
  {
    symbol: 'CELO',
    name: 'Celo Native Token',
    balance: BigInt('1000000000000000000000'), // 1000 CELO
    decimals: 18,
    formattedBalance: '1000.00',
    usdValue: 850.00, // 1000 * $0.85
    change24h: 2.5,
    contractAddress: '0x0000000000000000000000000000000000000000',
    category: 'native',
    isNative: true,
    lastUpdated: new Date()
  },
  {
    symbol: 'USDm',
    name: 'Mento Dollar',
    balance: BigInt('500000000000000000000'), // 500 USDm
    decimals: 18,
    formattedBalance: '500.00',
    usdValue: 500.00, // 500 * $1.00
    change24h: 0.01,
    contractAddress: '0x765de816845861e75a25fca122bb6898b8b1282a',
    category: 'mento',
    isNative: false,
    lastUpdated: new Date()
  },
  {
    symbol: 'USDC',
    name: 'USD Coin',
    balance: BigInt('200000000'), // 200 USDC (6 decimals)
    decimals: 6,
    formattedBalance: '200.00',
    usdValue: 200.00, // 200 * $1.00
    change24h: 0.0,
    contractAddress: '0xceba9300f2b948710d2653dd7b07f33a8b32118c',
    category: 'circle',
    isNative: false,
    lastUpdated: new Date()
  }
]

const mockPortfolioSummary: PortfolioSummary = {
  totalValueUsd: 1550.00,
  totalValueChange24h: 21.25,
  totalValueChangePercent24h: 1.37,
  tokenCount: 3,
  hasZeroBalanceTokens: false,
  networkName: 'Celo'
}

// Mock hooks
vi.mock('../hooks/useTokenBalances')
vi.mock('../services/tokenBalanceService')

const mockUseTokenBalances = vi.mocked(useTokenBalances)
const mockTokenBalanceService = vi.mocked(tokenBalanceService)

describe('WalletConnect Multi-Token Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Default mock implementations
    mockUseTokenBalances.mockReturnValue({
      portfolio: {
        address: '0x1234567890123456789012345678901234567890',
        chainId: celo.id,
        tokens: mockTokenBalances,
        totalValueUsd: 1550.00,
        totalValueChange24h: 21.25,
        lastUpdated: new Date(),
        isLoading: false,
        error: undefined
      },
      summary: mockPortfolioSummary,
      refreshState: {
        isRefreshing: false,
        lastRefreshTime: new Date(),
        refreshError: undefined,
        autoRefreshEnabled: true
      },
      refreshBalances: vi.fn(),
      toggleAutoRefresh: vi.fn(),
      isLoading: false,
      error: null
    })

    mockTokenBalanceService.sortTokens.mockReturnValue(mockTokenBalances)
    mockTokenBalanceService.formatBalance.mockImplementation((token, options) => {
      let formatted = token.formattedBalance
      if (options?.showSymbol) {
        formatted += ` ${token.symbol}`
      }
      if (options?.showUSDValue && token.usdValue) {
        formatted += ` ($${token.usdValue.toLocaleString()})`
      }
      return formatted
    })
  })

  test('renders wallet connect button when disconnected', () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <WalletConnect />
      </Wrapper>
    )

    expect(screen.getByText('Connect Wallet')).toBeInTheDocument()
  })

  test('displays multi-token portfolio when connected', async () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <WalletConnect />
      </Wrapper>
    )

    // Wait for portfolio to load
    await waitFor(() => {
      expect(screen.getByText('Token Portfolio')).toBeInTheDocument()
    })

    // Check portfolio summary
    expect(screen.getByText('$1,550.00')).toBeInTheDocument()
    expect(screen.getByText('3 tokens')).toBeInTheDocument()

    // Check individual tokens
    expect(screen.getByText('Celo Native Token')).toBeInTheDocument()
    expect(screen.getByText('Mento Dollar')).toBeInTheDocument()
    expect(screen.getByText('USD Coin')).toBeInTheDocument()
  })

  test('handles refresh functionality', async () => {
    const mockRefresh = vi.fn()
    mockUseTokenBalances.mockReturnValue({
      portfolio: {
        address: '0x1234567890123456789012345678901234567890',
        chainId: celo.id,
        tokens: mockTokenBalances,
        totalValueUsd: 1550.00,
        totalValueChange24h: 21.25,
        lastUpdated: new Date(),
        isLoading: false,
        error: undefined
      },
      summary: mockPortfolioSummary,
      refreshState: {
        isRefreshing: false,
        lastRefreshTime: new Date(),
        refreshError: undefined,
        autoRefreshEnabled: true
      },
      refreshBalances: mockRefresh,
      toggleAutoRefresh: vi.fn(),
      isLoading: false,
      error: null
    })

    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <WalletConnect />
      </Wrapper>
    )

    await waitFor(() => {
      expect(screen.getByTitle('Refresh balances')).toBeInTheDocument()
    })

    const refreshButton = screen.getByTitle('Refresh balances')
    fireEvent.click(refreshButton)

    expect(mockRefresh).toHaveBeenCalledTimes(1)
  })

  test('displays loading state correctly', async () => {
    mockUseTokenBalances.mockReturnValue({
      portfolio: {
        address: '0x1234567890123456789012345678901234567890',
        chainId: celo.id,
        tokens: [],
        totalValueUsd: 0,
        totalValueChange24h: 0,
        lastUpdated: new Date(),
        isLoading: true,
        error: undefined
      },
      summary: {
        totalValueUsd: 0,
        totalValueChange24h: 0,
        totalValueChangePercent24h: 0,
        tokenCount: 0,
        hasZeroBalanceTokens: false,
        networkName: 'Celo'
      },
      refreshState: {
        isRefreshing: false,
        lastRefreshTime: new Date(),
        refreshError: undefined,
        autoRefreshEnabled: true
      },
      refreshBalances: vi.fn(),
      toggleAutoRefresh: vi.fn(),
      isLoading: true,
      error: null
    })

    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <WalletConnect />
      </Wrapper>
    )

    await waitFor(() => {
      expect(screen.getByText('Loading balances...')).toBeInTheDocument()
    })
  })

  test('displays error state correctly', async () => {
    const errorMessage = 'Failed to fetch balances'
    mockUseTokenBalances.mockReturnValue({
      portfolio: {
        address: '0x1234567890123456789012345678901234567890',
        chainId: celo.id,
        tokens: [],
        totalValueUsd: 0,
        totalValueChange24h: 0,
        lastUpdated: new Date(),
        isLoading: false,
        error: errorMessage
      },
      summary: {
        totalValueUsd: 0,
        totalValueChange24h: 0,
        totalValueChangePercent24h: 0,
        tokenCount: 0,
        hasZeroBalanceTokens: false,
        networkName: 'Celo'
      },
      refreshState: {
        isRefreshing: false,
        lastRefreshTime: new Date(),
        refreshError: undefined,
        autoRefreshEnabled: true
      },
      refreshBalances: vi.fn(),
      toggleAutoRefresh: vi.fn(),
      isLoading: false,
      error: errorMessage
    })

    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <WalletConnect />
      </Wrapper>
    )

    await waitFor(() => {
      expect(screen.getByText(errorMessage)).toBeInTheDocument()
    })
  })
})

describe('TokenPortfolio Component', () => {
  const mockProps = {
    portfolio: {
      address: '0x1234567890123456789012345678901234567890',
      chainId: celo.id,
      tokens: mockTokenBalances,
      totalValueUsd: 1550.00,
      totalValueChange24h: 21.25,
      lastUpdated: new Date(),
      isLoading: false,
      error: undefined
    },
    summary: mockPortfolioSummary,
    refreshState: {
      isRefreshing: false,
      lastRefreshTime: new Date(),
      refreshError: undefined,
      autoRefreshEnabled: true
    },
    onRefresh: vi.fn(),
    onToggleAutoRefresh: vi.fn()
  }

  test('renders portfolio summary correctly', () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TokenPortfolio {...mockProps} />
      </Wrapper>
    )

    expect(screen.getByText('Token Portfolio')).toBeInTheDocument()
    expect(screen.getByText('$1,550.00')).toBeInTheDocument()
    expect(screen.getByText('$21.25')).toBeInTheDocument()
    expect(screen.getByText('1.37%')).toBeInTheDocument()
    expect(screen.getByText('3 tokens')).toBeInTheDocument()
  })

  test('displays individual tokens with correct information', () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TokenPortfolio {...mockProps} />
      </Wrapper>
    )

    // Check CELO token
    expect(screen.getByText('Celo Native Token')).toBeInTheDocument()
    expect(screen.getByText('1000.00 CELO')).toBeInTheDocument()
    expect(screen.getByText('$850.00')).toBeInTheDocument()

    // Check USDm token
    expect(screen.getByText('Mento Dollar')).toBeInTheDocument()
    expect(screen.getByText('500.00 USDm')).toBeInTheDocument()
    expect(screen.getByText('$500.00')).toBeInTheDocument()
  })

  test('handles copy address functionality', async () => {
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined)
    }
    Object.assign(navigator, { clipboard: mockClipboard })

    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TokenPortfolio {...mockProps} />
      </Wrapper>
    )

    const copyButtons = screen.getAllByText('Copy')
    fireEvent.click(copyButtons[0])

    await waitFor(() => {
      expect(mockClipboard.writeText).toHaveBeenCalledWith(
        '0x765de816845861e75a25fca122bb6898b8b1282a'
      )
    })

    expect(screen.getByText('Copied!')).toBeInTheDocument()
  })

  test('shows empty state when no tokens', () => {
    const emptyProps = {
      ...mockProps,
      portfolio: {
        ...mockProps.portfolio,
        tokens: []
      },
      summary: {
        ...mockProps.summary,
        tokenCount: 0
      }
    }

    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TokenPortfolio {...emptyProps} />
      </Wrapper>
    )

    expect(screen.getByText('No tokens found')).toBeInTheDocument()
    expect(screen.getByText('Your token balances will appear here')).toBeInTheDocument()
  })

  test('renders compact view correctly', () => {
    const Wrapper = createTestWrapper()
    
    render(
      <Wrapper>
        <TokenPortfolio {...mockProps} compact={true} />
      </Wrapper>
    )

    expect(screen.getByText('Portfolio Value')).toBeInTheDocument()
    expect(screen.getByText('$1,550.00')).toBeInTheDocument()
    expect(screen.getByText('3 tokens')).toBeInTheDocument()
  })
})

describe('TokenBalanceService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('calculates USD values correctly', () => {
    const tokenBalance: TokenBalance = {
      symbol: 'USDm',
      name: 'Mento Dollar',
      balance: BigInt('1000000000000000000000'), // 1000 tokens
      decimals: 18,
      formattedBalance: '1000.00',
      contractAddress: '0x765de816845861e75a25fca122bb6898b8b1282a',
      category: 'mento',
      isNative: false,
      lastUpdated: new Date()
    }

    const usdValue = tokenBalanceService.calculateUSDValue(tokenBalance)
    expect(usdValue).toBe(1000.00) // 1000 * $1.00
  })

  test('sorts tokens by priority and value', () => {
    const unsortedTokens: TokenBalance[] = [
      {
        symbol: 'USDC',
        name: 'USD Coin',
        balance: BigInt('100000000'), // 100 USDC
        decimals: 6,
        formattedBalance: '100.00',
        usdValue: 100.00,
        contractAddress: '0xceba9300f2b948710d2653dd7b07f33a8b32118c',
        category: 'circle',
        isNative: false,
        lastUpdated: new Date()
      },
      {
        symbol: 'CELO',
        name: 'Celo Native Token',
        balance: BigInt('100000000000000000000'), // 100 CELO
        decimals: 18,
        formattedBalance: '100.00',
        usdValue: 85.00, // 100 * $0.85
        contractAddress: '0x0000000000000000000000000000000000000000',
        category: 'native',
        isNative: true,
        lastUpdated: new Date()
      },
      {
        symbol: 'USDm',
        name: 'Mento Dollar',
        balance: BigInt('500000000000000000000'), // 500 USDm
        decimals: 18,
        formattedBalance: '500.00',
        usdValue: 500.00,
        contractAddress: '0x765de816845861e75a25fca122bb6898b8b1282a',
        category: 'mento',
        isNative: false,
        lastUpdated: new Date()
      }
    ]

    const sortedTokens = tokenBalanceService.sortTokens(unsortedTokens)

    // CELO should be first (native token)
    expect(sortedTokens[0].symbol).toBe('CELO')
    // USDm should be second (priority token with highest value)
    expect(sortedTokens[1].symbol).toBe('USDm')
    // USDC should be third
    expect(sortedTokens[2].symbol).toBe('USDC')
  })

  test('filters tokens correctly', () => {
    const tokens: TokenBalance[] = [
      {
        symbol: 'CELO',
        name: 'Celo Native Token',
        balance: BigInt('1000000000000000000000'),
        decimals: 18,
        formattedBalance: '1000.00',
        contractAddress: '0x0000000000000000000000000000000000000000',
        category: 'native',
        isNative: true,
        lastUpdated: new Date()
      },
      {
        symbol: 'USDm',
        name: 'Mento Dollar',
        balance: BigInt('0'), // Zero balance
        decimals: 18,
        formattedBalance: '0.00',
        contractAddress: '0x765de816845861e75a25fca122bb6898b8b1282a',
        category: 'mento',
        isNative: false,
        lastUpdated: new Date()
      }
    ]

    const filteredTokens = tokenBalanceService.filterTokens(tokens, {
      includeZeroBalances: false
    })

    expect(filteredTokens).toHaveLength(1)
    expect(filteredTokens[0].symbol).toBe('CELO')
  })

  test('calculates portfolio summary correctly', () => {
    const summary = tokenBalanceService.calculatePortfolioSummary(mockTokenBalances)

    expect(summary.totalValueUsd).toBe(1550.00)
    expect(summary.totalValueChange24h).toBe(21.25)
    expect(summary.totalValueChangePercent24h).toBeCloseTo(1.37, 2)
    expect(summary.tokenCount).toBe(3)
    expect(summary.hasZeroBalanceTokens).toBe(false)
  })
})

describe('Token Registry', () => {
  test('contains all expected tokens', () => {
    const expectedTokens = [
      'CELO', 'USDm', 'EURm', 'BRLm', 'USDC', 'USDT',
      'cUSD', 'cEUR', 'vEUR', 'vGBP', 'USDM', 'USDA'
    ]

    expectedTokens.forEach(symbol => {
      expect(TOKEN_REGISTRY[symbol]).toBeDefined()
      expect(TOKEN_REGISTRY[symbol].symbol).toBe(symbol)
    })
  })

  test('provides correct contract addresses for networks', () => {
    const { getTokenContractAddress } = require('../lib/token-registry')

    // Test mainnet address
    const mainnetAddress = getTokenContractAddress('USDm', celo.id)
    expect(mainnetAddress).toBe('0x765de816845861e75a25fca122bb6898b8b1282a')

    // Test sepolia address
    const sepoliaAddress = getTokenContractAddress('USDm', celoAlfajores.id)
    expect(sepoliaAddress).toBe('0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b')
  })

  test('filters tokens by category', () => {
    const { getTokensByCategory } = require('../lib/token-registry')

    const mentoTokens = getTokensByCategory('mento')
    expect(mentoTokens.length).toBeGreaterThan(0)
    expect(mentoTokens.every(token => token.category === 'mento')).toBe(true)

    const nativeTokens = getTokensByCategory('native')
    expect(nativeTokens).toHaveLength(1)
    expect(nativeTokens[0].symbol).toBe('CELO')
  })

  test('gets tokens for specific network', () => {
    const { getTokensForNetwork } = require('../lib/token-registry')

    const mainnetTokens = getTokensForNetwork(celo.id)
    expect(mainnetTokens.length).toBeGreaterThan(0)

    const sepoliaTokens = getTokensForNetwork(celoAlfajores.id)
    expect(sepoliaTokens.length).toBeGreaterThan(0)

    // Some tokens might not be deployed on Sepolia
    expect(sepoliaTokens.length).toBeLessThanOrEqual(mainnetTokens.length)
  })
})
