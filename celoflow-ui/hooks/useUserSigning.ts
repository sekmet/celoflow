/**
 * useUserSigning — React hook for user wallet signing flow.
 *
 * Manages the state machine for preparing, signing, and executing
 * user-signed transactions via the connected wallet (wagmi).
 */

import { useState, useCallback } from 'react'
import { useAccount, useSendTransaction, useWaitForTransactionReceipt } from 'wagmi'
import {
  prepareTransfer,
  executeSignedTransfer,
  rejectTransfer,
  type PreparedTransfer,
  type TransferResult,
  type PrepareTransferRequest,
} from '../lib/user-signing-client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SigningStep =
  | 'idle'
  | 'preparing'
  | 'awaiting_choice'      // User chooses TEE or user wallet
  | 'awaiting_signature'   // Waiting for wallet signature
  | 'broadcasting'         // Signed tx being broadcast
  | 'confirmed'            // Transaction confirmed
  | 'failed'               // Something went wrong
  | 'rejected'             // User rejected

export interface UserSigningState {
  step: SigningStep
  preparedTransfer: PreparedTransfer | null
  result: TransferResult | null
  error: string | null
  isLoading: boolean
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useUserSigning() {
  const { address, isConnected } = useAccount()
  const { sendTransactionAsync } = useSendTransaction()

  const [state, setState] = useState<UserSigningState>({
    step: 'idle',
    preparedTransfer: null,
    result: null,
    error: null,
    isLoading: false,
  })

  /**
   * Prepare a transfer for user signing.
   * Returns the prepared transfer data including tx_data and gas estimates.
   */
  const prepare = useCallback(async (
    recipientAddress: string,
    amount: number,
    token: string,
  ): Promise<PreparedTransfer | null> => {
    if (!isConnected || !address) {
      setState(prev => ({
        ...prev,
        step: 'failed',
        error: 'Wallet not connected',
      }))
      return null
    }

    setState(prev => ({
      ...prev,
      step: 'preparing',
      isLoading: true,
      error: null,
    }))

    try {
      const request: PrepareTransferRequest = {
        user_address: address,
        recipient_address: recipientAddress,
        amount,
        token,
        chain_id: 44787, // Celo Sepolia
      }

      const prepared = await prepareTransfer(request)

      setState(prev => ({
        ...prev,
        step: 'awaiting_choice',
        preparedTransfer: prepared,
        isLoading: false,
      }))

      return prepared
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to prepare transfer'
      setState(prev => ({
        ...prev,
        step: 'failed',
        error: errorMsg,
        isLoading: false,
      }))
      return null
    }
  }, [address, isConnected])

  /**
   * Sign and execute the prepared transfer using the user's wallet.
   */
  const signAndExecute = useCallback(async (): Promise<TransferResult | null> => {
    const { preparedTransfer } = state
    if (!preparedTransfer || !preparedTransfer.tx_data) {
      setState(prev => ({
        ...prev,
        step: 'failed',
        error: 'No prepared transfer to sign',
      }))
      return null
    }

    setState(prev => ({
      ...prev,
      step: 'awaiting_signature',
      isLoading: true,
      error: null,
    }))

    try {
      const txData = preparedTransfer.tx_data

      // Send transaction via wagmi (prompts user's wallet)
      const hash = await sendTransactionAsync({
        to: txData.to as `0x${string}`,
        data: txData.data as `0x${string}` | undefined,
        value: txData.value ? BigInt(txData.value as string) : BigInt(0),
        gas: txData.gas ? BigInt(txData.gas as string) : undefined,
      })

      setState(prev => ({
        ...prev,
        step: 'broadcasting',
      }))

      // The hash is the tx hash from the user's wallet
      const result: TransferResult = {
        status: 'success',
        tx_hash: hash,
        amount: preparedTransfer.amount,
        token: preparedTransfer.token,
        recipient: preparedTransfer.recipient_address,
        signer_type: 'user',
        explorer_url: `https://sepolia.celoscan.io/tx/${hash}`,
      }

      setState(prev => ({
        ...prev,
        step: 'confirmed',
        result,
        isLoading: false,
      }))

      return result
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Signing failed'
      const isRejection = errorMsg.includes('rejected') || errorMsg.includes('denied')

      setState(prev => ({
        ...prev,
        step: isRejection ? 'rejected' : 'failed',
        error: isRejection ? 'Transaction rejected by user' : errorMsg,
        isLoading: false,
      }))

      // If rejected, notify backend
      if (isRejection && state.preparedTransfer) {
        try {
          await rejectTransfer(state.preparedTransfer.transfer_id)
        } catch {
          // Non-critical
        }
      }

      return null
    }
  }, [state, sendTransactionAsync])

  /**
   * Reset the signing state back to idle.
   */
  const reset = useCallback(() => {
    setState({
      step: 'idle',
      preparedTransfer: null,
      result: null,
      error: null,
      isLoading: false,
    })
  }, [])

  /**
   * Reject the current prepared transfer.
   */
  const reject = useCallback(async () => {
    if (state.preparedTransfer) {
      try {
        await rejectTransfer(state.preparedTransfer.transfer_id)
      } catch {
        // Non-critical
      }
    }
    setState(prev => ({
      ...prev,
      step: 'rejected',
      error: 'Transfer cancelled by user',
      isLoading: false,
    }))
  }, [state.preparedTransfer])

  return {
    ...state,
    isWalletConnected: isConnected,
    walletAddress: address,
    prepare,
    signAndExecute,
    reset,
    reject,
  }
}
