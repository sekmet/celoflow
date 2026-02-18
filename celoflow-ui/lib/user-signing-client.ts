/**
 * User Signing Client — API client for user wallet signing flow.
 *
 * Handles communication with the backend's /transfer/* endpoints
 * for preparing, executing, and managing user-signed transactions.
 */

import { CELOFLOW_API_URL } from './celoflow-client'
import { authService } from './auth-service'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PrepareTransferRequest {
  user_address: string
  recipient_address: string
  amount: number
  token: string
  chain_id?: number
}

export interface AutoSwapStep {
  step: number
  description: string
  action: string
  token?: string
  from_token?: string
  to_token?: string
  spender?: string
  exchange_id?: string
  error?: string
}

export interface PreparedTransfer {
  transfer_id: string
  signer_type: 'tee' | 'user'
  recipient_address: string
  amount: number
  token: string
  resolved_token: string
  token_address: string
  decimals: number
  amount_wei: number
  chain_id: number
  status: 'pending' | 'signed' | 'broadcasting' | 'confirmed' | 'failed' | 'expired' | 'rejected'
  tx_data: Record<string, unknown> | null
  needs_auto_swap: boolean
  auto_swap_steps: AutoSwapStep[]
  estimated_gas: number
  gas_price_wei: number
  estimated_gas_cost_eth: number
  created_at: number
  expires_at: number
  user_address: string | null
  signed_tx: string | null
  tx_hash: string | null
  error: string | null
}

export interface TransferResult {
  status: string
  tx_hash?: string
  amount?: number
  token?: string
  recipient?: string
  signer_type?: string
  explorer_url?: string
  error?: string
  note?: string
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

function getBaseUrl(): string {
  const raw = CELOFLOW_API_URL || 'http://localhost:8000'
  return raw.endsWith('/') ? raw.slice(0, -1) : raw
}

/**
 * Prepare an unsigned transfer for user wallet signing.
 */
export async function prepareTransfer(
  request: PrepareTransferRequest,
): Promise<PreparedTransfer> {
  const base = getBaseUrl()
  const authHeaders = await authService.getAuthHeaders()

  const response = await fetch(`${base}/transfer/prepare`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(request),
  })

  const data = await response.json()
  if (data.error) {
    throw new Error(data.error)
  }
  return data as PreparedTransfer
}

/**
 * Execute a user-signed transfer by broadcasting it.
 */
export async function executeSignedTransfer(
  transferId: string,
  signedTx: string,
): Promise<TransferResult> {
  const base = getBaseUrl()
  const authHeaders = await authService.getAuthHeaders()

  const response = await fetch(`${base}/transfer/execute`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify({
      transfer_id: transferId,
      signed_tx: signedTx,
    }),
  })

  const data = await response.json()
  return data as TransferResult
}

/**
 * Get the status of a prepared transfer.
 */
export async function getTransferStatus(
  transferId: string,
): Promise<PreparedTransfer | null> {
  const base = getBaseUrl()
  const authHeaders = await authService.getAuthHeaders()

  const response = await fetch(`${base}/transfer/${transferId}`, {
    headers: authHeaders,
  })

  if (response.status === 404) return null
  const data = await response.json()
  return data as PreparedTransfer
}

/**
 * Reject/cancel a pending transfer.
 */
export async function rejectTransfer(
  transferId: string,
): Promise<{ status: string; transfer_id: string }> {
  const base = getBaseUrl()
  const authHeaders = await authService.getAuthHeaders()

  const response = await fetch(`${base}/transfer/${transferId}/reject`, {
    method: 'POST',
    headers: authHeaders,
  })

  return response.json()
}

/**
 * Get all pending transfers for a user address.
 */
export async function getPendingTransfers(
  userAddress: string,
): Promise<PreparedTransfer[]> {
  const base = getBaseUrl()
  const authHeaders = await authService.getAuthHeaders()

  const response = await fetch(`${base}/transfer/pending/${userAddress}`, {
    headers: authHeaders,
  })

  const data = await response.json()
  return data.transfers || []
}
