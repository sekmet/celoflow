/**
 * Wagmi Configuration for CeloFlow UI
 *
 * Configures wallet connectors and Celo chains for EVM wallet connectivity.
 * Supports custom RPC endpoints and chain IDs via environment variables.
 */

import { http, createConfig } from 'wagmi'
import { celo, celoAlfajores } from 'wagmi/chains'
import { injected, metaMask } from 'wagmi/connectors'
import { QueryClient } from '@tanstack/react-query'

// Environment variables for blockchain configuration
const customRpcUrl = import.meta.env.VITE_CELO_RPC_URL
const customChainId = import.meta.env.VITE_CELO_CHAIN_ID

// Create custom chain configuration if environment variables are provided
const createCustomChain = () => {
  if (customRpcUrl && customChainId) {
    const chainId = parseInt(customChainId)
    if (!isNaN(chainId)) {
      console.log(`[wagmi-config] Using custom RPC: ${customRpcUrl}`)
      console.log(`[wagmi-config] Using custom chain ID: ${chainId}`)
      
      return {
        id: chainId,
        name: 'Celo Custom',
        nativeCurrency: {
          name: 'CELO',
          symbol: 'CELO',
          decimals: 18,
        },
        rpcUrls: {
          default: {
            http: [customRpcUrl],
          },
          public: {
            http: [customRpcUrl],
          },
        },
        blockExplorers: {
          default: {
            name: 'Celo Explorer',
            url: 'https://explorer.celo.org',
          },
        },
        testnet: chainId !== 42220, // Assume testnet unless it's mainnet
      }
    }
  }
  return null
}

const customChain = createCustomChain()

export const config = createConfig({
  chains: customChain ? [customChain] : [celo, celoAlfajores],
  connectors: [
    injected(),
    metaMask(),
  ],
  transports: customChain 
    ? {
        [customChain.id]: http(customRpcUrl),
      }
    : {
        [celo.id]: http(),
        [celoAlfajores.id]: http(),
      },
})

export const queryClient = new QueryClient()

// Re-export chain info for use in components
export { celo, celoAlfajores }
export { customChain }
