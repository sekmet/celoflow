/**
 * CeloFlow Streaming Chat Client
 *
 * Pure client-side SSE streaming chat client that connects to the celoflow
 * backend. No server-side calls — suitable for Cloudflare Pages/Workers.
 *
 * Pattern adapted from contextwise-agent-ui's openai-client.ts
 */

// Default to localhost:8000 for local development; override via VITE_CELOFLOW_API_URL
export const CELOFLOW_API_URL: string =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_CELOFLOW_API_URL) ||
  'http://localhost:8000'

function normalizeUrl(rawUrl: string): string {
  const trimmed = rawUrl.trim()
  if (!trimmed) return 'http://localhost:8000'

  try {
    const url = new URL(trimmed)
    if (url.hostname === '0.0.0.0' || url.hostname === '::') {
      url.hostname = 'localhost'
    }
    const normalized = url.toString()
    return normalized.endsWith('/') ? normalized.slice(0, -1) : normalized
  } catch {
    return trimmed
  }
}

function getBaseUrl(override?: string): string {
  const candidate = override?.trim() || CELOFLOW_API_URL
  return normalizeUrl(candidate)
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface WalletContext {
  wallet_address?: string
  connected: boolean
  chain_id?: number
  balances: Record<string, string>
}

/** Callback receives full accumulated content + the latest delta */
export type OnStreamContentCallback = (fullContent: string, delta: string) => void

export interface ContactData {
  id: string
  name: string
  address: string
  network: string
  city: string
  country: string
  phone: string
  email: string
  notes: string
  favorite: boolean
  blocked: boolean
  group: string
}

export interface StreamChatOptions {
  messages: ChatMessage[]
  conversation_id?: string
  baseUrl?: string
  walletContext?: WalletContext
  contacts?: ContactData[]
  onContent?: OnStreamContentCallback
  onComplete?: (fullContent: string) => void
  onError?: (error: Error) => void
  signal?: AbortSignal
}

export interface SendChatOptions {
  messages: ChatMessage[]
  conversation_id?: string
  baseUrl?: string
  walletContext?: WalletContext
  contacts?: ContactData[]
  signal?: AbortSignal
}

// ---------------------------------------------------------------------------
// Streaming Chat (SSE)
// ---------------------------------------------------------------------------

/**
 * Stream chat response from celoflow backend via Server-Sent Events.
 *
 * Uses `POST /chat/stream` with OpenAI-compatible SSE format:
 *   data: {"choices":[{"delta":{"content":"..."}}]}
 *   data: [DONE]
 *
 * @returns The full accumulated content string
 */
export async function streamChat(options: StreamChatOptions): Promise<string> {
  const {
    messages,
    conversation_id,
    baseUrl,
    walletContext,
    contacts,
    onContent,
    onComplete,
    onError,
    signal,
  } = options

  const endpointBase = getBaseUrl(baseUrl)

  try {
    // Prepare request body with wallet context and contacts
    const requestBody = {
      messages,
      conversation_id,
      ...(walletContext && { wallet_context: walletContext }),
      ...(contacts && contacts.length > 0 && { contacts }),
    }

    const response = await fetch(`${endpointBase}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(requestBody),
      signal,
    })

    if (!response.ok) {
      const body = await response.text()
      throw new Error(
        `Chat stream error: ${response.status} ${response.statusText} — ${body}`,
      )
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Response body is not readable')
    }

    let fullContent = ''
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const trimmed = line.trimEnd()
          if (trimmed.startsWith('data:')) {
            const data = trimmed.slice(5).trimStart()
            if (data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)

              // Handle error responses embedded in SSE
              if (parsed.error) {
                throw new Error(parsed.error.message || 'Streaming error')
              }

              // Extract content delta (OpenAI-compatible format)
              const delta = parsed.choices?.[0]?.delta?.content
              if (delta) {
                fullContent += delta
                onContent?.(fullContent, delta)
              }
            } catch (parseError) {
              if (
                parseError instanceof Error &&
                parseError.message !== 'Streaming error'
              ) {
                console.debug('Failed to parse SSE data:', data)
              } else {
                throw parseError
              }
            }
          }
        }
      }

      // Process any remaining buffered data
      const trailing = buffer.trim()
      if (trailing.startsWith('data:')) {
        const data = trailing.slice(5).trimStart()
        if (data !== '[DONE]') {
          try {
            const parsed = JSON.parse(data)
            if (parsed?.error) {
              throw new Error(parsed.error.message || 'Streaming error')
            }
            const delta = parsed?.choices?.[0]?.delta?.content
            if (delta) {
              fullContent += delta
              onContent?.(fullContent, delta)
            }
          } catch {
            // Ignore trailing parse errors
          }
        }
      }
    } finally {
      reader.releaseLock()
    }

    onComplete?.(fullContent)
    return fullContent
  } catch (error) {
    const err = error instanceof Error ? error : new Error(String(error))
    onError?.(err)
    throw err
  }
}

// ---------------------------------------------------------------------------
// Non-streaming Chat (fallback)
// ---------------------------------------------------------------------------

/**
 * Send a non-streaming chat request to celoflow backend.
 *
 * Uses `POST /chat` and returns the full response content.
 */
export async function sendChat(options: SendChatOptions): Promise<string> {
  const { messages, conversation_id, baseUrl, walletContext, contacts, signal } = options
  const endpointBase = getBaseUrl(baseUrl)

  // Prepare request body with wallet context and contacts
  const requestBody = {
    messages,
    conversation_id,
    ...(walletContext && { wallet_context: walletContext }),
    ...(contacts && contacts.length > 0 && { contacts }),
  }

  const response = await fetch(`${endpointBase}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    const body = await response.text()
    throw new Error(
      `Chat error: ${response.status} ${response.statusText} — ${body}`,
    )
  }

  const json = (await response.json()) as any
  return json?.choices?.[0]?.message?.content ?? ''
}

// ---------------------------------------------------------------------------
// Streaming Support Check
// ---------------------------------------------------------------------------

/**
 * Quick check if the backend supports the /chat/stream endpoint.
 */
export async function checkStreamingSupport(baseUrl?: string): Promise<boolean> {
  const endpointBase = getBaseUrl(baseUrl)
  try {
    const response = await fetch(`${endpointBase}/chat/stream`, {
      method: 'OPTIONS',
      signal: AbortSignal.timeout(3000),
    })
    return response.status !== 404
  } catch {
    return false
  }
}
