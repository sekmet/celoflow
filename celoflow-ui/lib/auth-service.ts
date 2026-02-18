/**
 * CeloFlow Authentication Service
 *
 * Manages JWT token lifecycle for the celoflow-ui frontend:
 * - Login (origin-based or wallet-based)
 * - Automatic token refresh before expiry
 * - Logout with token revocation
 * - Token persistence in localStorage
 * - Conditional TEE attestation client
 */

import { CELOFLOW_API_URL } from './celoflow-client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthTokens {
  access_token: string
  refresh_token: string
  expires_in: number
  token_type: string
  tee_verified: boolean
}

export interface AuthState {
  authenticated: boolean
  tokens: AuthTokens | null
  expiresAt: number | null
  method: string | null
  teeVerified: boolean
}

export interface AttestationInfo {
  enabled: boolean
  available?: boolean
  mode?: string
  address?: string
  domain?: string
  has_quote?: boolean
  error?: string
  message?: string
}

type AuthStateListener = (state: AuthState) => void

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'celoflow_auth'
const REFRESH_MARGIN_MS = 60_000 // Refresh 60s before expiry

// ---------------------------------------------------------------------------
// Auth Service
// ---------------------------------------------------------------------------

class AuthServiceClient {
  private state: AuthState = {
    authenticated: false,
    tokens: null,
    expiresAt: null,
    method: null,
    teeVerified: false,
  }

  private listeners: Set<AuthStateListener> = new Set()
  private refreshTimer: ReturnType<typeof setTimeout> | null = null
  private baseUrl: string
  private loginPromise: Promise<AuthState> | null = null

  constructor() {
    this.baseUrl = this.getBaseUrl()
    this.loadFromStorage()
  }

  // ── Public API ─────────────────────────────────────────────

  /**
   * Login to the CeloFlow API.
   * Uses origin-based auth by default; optionally pass wallet address or API key.
   */
  async login(options?: {
    walletAddress?: string
    apiKey?: string
  }): Promise<AuthState> {
    // Deduplicate simultaneous login attempts
    if (this.loginPromise) {
      console.debug('[AuthService] Login already in progress, waiting...')
      return this.loginPromise
    }

    this.loginPromise = this._performLogin(options)
    
    try {
      const result = await this.loginPromise
      return result
    } finally {
      this.loginPromise = null
    }
  }

  private async _performLogin(options?: {
    walletAddress?: string
    apiKey?: string
  }): Promise<AuthState> {
    const url = `${this.baseUrl}/auth/login`

    const body: Record<string, string> = {}
    if (options?.walletAddress) body.wallet_address = options.walletAddress
    if (options?.apiKey) body.api_key = options.apiKey

    try {
      console.debug('[AuthService] Login attempt:', { url, body })
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const data = await response.json()
      console.debug('[AuthService] Login response:', { status: response.status, data })

      if (!response.ok || !data.success) {
        this.clearState()
        throw new Error(data.error || 'Authentication failed')
      }

      const tokens: AuthTokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_in: data.expires_in,
        token_type: data.token_type || 'Bearer',
        tee_verified: data.tee_verified || false,
      }

      this.setState({
        authenticated: true,
        tokens,
        expiresAt: Date.now() + tokens.expires_in * 1000,
        method: options?.apiKey ? 'api_key' : options?.walletAddress ? 'wallet' : 'origin',
        teeVerified: tokens.tee_verified,
      })

      this.scheduleRefresh()
      return this.state
    } catch (error) {
      this.clearState()
      throw error
    }
  }

  /**
   * Refresh the access token using the stored refresh token.
   */
  async refresh(): Promise<boolean> {
    if (!this.state.tokens?.refresh_token) return false

    const url = `${this.baseUrl}/auth/refresh`

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          refresh_token: this.state.tokens.refresh_token,
        }),
      })

      const data = await response.json()

      if (!response.ok || !data.success) {
        this.clearState()
        return false
      }

      this.setState({
        ...this.state,
        tokens: {
          ...this.state.tokens,
          access_token: data.access_token,
          expires_in: data.expires_in,
        },
        expiresAt: Date.now() + data.expires_in * 1000,
      })

      this.scheduleRefresh()
      return true
    } catch {
      this.clearState()
      return false
    }
  }

  /**
   * Logout and revoke the current token.
   */
  async logout(): Promise<void> {
    if (this.state.tokens?.access_token) {
      try {
        await fetch(`${this.baseUrl}/auth/logout`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${this.state.tokens.access_token}`,
          },
        })
      } catch {
        // Best-effort revocation
      }
    }
    this.clearState()
  }

  /**
   * Get TEE attestation information from the server.
   */
  async getAttestationInfo(): Promise<AttestationInfo> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/attestation`)
      return await response.json()
    } catch {
      return { enabled: false, error: 'Failed to fetch attestation info' }
    }
  }

  /**
   * Get the current access token for use in request headers.
   * Automatically refreshes if close to expiry.
   */
  async getAccessToken(): Promise<string | null> {
    if (!this.state.authenticated || !this.state.tokens) return null

    // Auto-refresh if within margin
    if (this.state.expiresAt && Date.now() > this.state.expiresAt - REFRESH_MARGIN_MS) {
      const refreshed = await this.refresh()
      if (!refreshed) return null
    }

    return this.state.tokens.access_token
  }

  /**
   * Get authorization headers for API requests.
   */
  async getAuthHeaders(): Promise<Record<string, string>> {
    // If not authenticated, try to login first
    if (!this.state.authenticated) {
      console.debug('[AuthService] Not authenticated, attempting login')
      try {
        await this.login()
      } catch {
        console.debug('[AuthService] Auto-login failed, proceeding without auth')
        return {}
      }
    }

    const token = await this.getAccessToken()
    console.debug('[AuthService] getAuthHeaders:', { 
      authenticated: this.state.authenticated, 
      hasToken: !!token, 
      tokenPreview: token ? `${token.substring(0, 20)}...` : 'none' 
    })
    if (!token) return {}
    return { Authorization: `Bearer ${token}` }
  }

  /**
   * Check if the user is currently authenticated.
   */
  isAuthenticated(): boolean {
    if (!this.state.authenticated || !this.state.expiresAt) return false
    return Date.now() < this.state.expiresAt
  }

  /**
   * Get the current auth state.
   */
  getState(): AuthState {
    return { ...this.state }
  }

  /**
   * Clear all stored auth data (useful for debugging corrupted state).
   */
  clearStoredData(): void {
    console.debug('[AuthService] Clearing all stored data')
    this.clearState()
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // localStorage may be unavailable
    }
  }

  /**
   * Subscribe to auth state changes.
   */
  subscribe(listener: AuthStateListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  // ── Internal ───────────────────────────────────────────────

  private getBaseUrl(): string {
    const raw =
      (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_CELOFLOW_API_URL) ||
      CELOFLOW_API_URL
    return raw.replace(/\/$/, '')
  }

  private setState(newState: AuthState): void {
    this.state = newState
    this.saveToStorage()
    this.notifyListeners()
  }

  private clearState(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer)
      this.refreshTimer = null
    }
    // Clear any in-progress login
    this.loginPromise = null
    this.setState({
      authenticated: false,
      tokens: null,
      expiresAt: null,
      method: null,
      teeVerified: false,
    })
  }

  private notifyListeners(): void {
    for (const listener of this.listeners) {
      try {
        listener(this.state)
      } catch {
        // Ignore listener errors
      }
    }
  }

  private scheduleRefresh(): void {
    if (this.refreshTimer) clearTimeout(this.refreshTimer)
    if (!this.state.expiresAt) return

    const delay = Math.max(0, this.state.expiresAt - Date.now() - REFRESH_MARGIN_MS)
    this.refreshTimer = setTimeout(() => {
      this.refresh().catch(() => {
        // Silent refresh failure — user will be prompted on next request
      })
    }, delay)
  }

  private saveToStorage(): void {
    try {
      if (this.state.authenticated && this.state.tokens) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
          tokens: this.state.tokens,
          expiresAt: this.state.expiresAt,
          method: this.state.method,
          teeVerified: this.state.teeVerified,
        }))
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch {
      // localStorage may be unavailable
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (!stored) return

      const data = JSON.parse(stored)
      if (!data.tokens || !data.expiresAt) {
        console.debug('[AuthService] Invalid stored data, clearing')
        localStorage.removeItem(STORAGE_KEY)
        return
      }

      // Check if token is still valid
      if (Date.now() >= data.expiresAt) {
        console.debug('[AuthService] Stored token expired, clearing')
        localStorage.removeItem(STORAGE_KEY)
        return
      }

      // Validate token structure
      if (!data.tokens.access_token || !data.tokens.refresh_token) {
        console.debug('[AuthService] Invalid token structure in storage, clearing')
        localStorage.removeItem(STORAGE_KEY)
        return
      }

      this.state = {
        authenticated: true,
        tokens: data.tokens,
        expiresAt: data.expiresAt,
        method: data.method || null,
        teeVerified: data.teeVerified || false,
      }

      console.debug('[AuthService] Loaded state from storage:', { 
        method: this.state.method, 
        teeVerified: this.state.teeVerified,
        expiresAt: new Date(this.state.expiresAt).toISOString()
      })
      this.scheduleRefresh()
    } catch (error) {
      console.debug('[AuthService] Error loading from storage, clearing:', error)
      localStorage.removeItem(STORAGE_KEY)
    }
  }
}

// Singleton instance
export const authService = new AuthServiceClient()
