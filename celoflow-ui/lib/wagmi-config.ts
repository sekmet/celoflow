/**
 * Wagmi Configuration for CeloFlow UI
 *
 * Configures wallet connectors and Celo chains for EVM wallet connectivity.
 * Pure client-side — no server-side dependencies.
 */

import { http, createConfig } from 'wagmi'
import { celo, celoAlfajores } from 'wagmi/chains'
import { injected, metaMask } from 'wagmi/connectors'
import { QueryClient } from '@tanstack/react-query'

export const config = createConfig({
  chains: [celo, celoAlfajores],
  connectors: [
    injected(),
    metaMask(),
  ],
  transports: {
    [celo.id]: http(),
    [celoAlfajores.id]: http(),
  },
})

export const queryClient = new QueryClient()

// Re-export chain info for use in components
export { celo, celoAlfajores }
