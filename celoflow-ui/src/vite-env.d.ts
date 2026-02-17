/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CELOFLOW_API_URL: string
  readonly VITE_CELO_RPC_URL?: string
  readonly VITE_CELO_CHAIN_ID?: string
  // Add other environment variables as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
