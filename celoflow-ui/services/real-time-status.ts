/** Real-time Status Service — Connects to backend SSE endpoint for live operation updates. */

export interface RealTimeStatusEvent {
  operation: 'swapping' | 'transferring' | 'checking_balance' | 'compliance_check' | 'tee_verification' | 'kyc_check' | 'route_finding' | 'error' | 'idle';
  message: string;
  details?: {
    amount?: string;
    token?: string;
    recipient?: string;
    transaction_hash?: string;
    current_balance?: string;
    needed_amount?: string;
    error_message?: string;
    progress?: number;
  };
  timestamp: number;
  progress?: number;
  transaction_hash?: string;
  amount?: string;
  token?: string;
  recipient?: string;
}

export interface StatusConnectionState {
  connected: boolean;
  lastEvent?: RealTimeStatusEvent;
  error?: string;
  reconnectAttempts: number;
}

export class RealTimeStatusService {
  private eventSource?: EventSource;
  private subscribers: Set<(event: RealTimeStatusEvent) => void> = new Set();
  private connectionSubscribers: Set<(state: StatusConnectionState) => void> = new Set();
  private connectionState: StatusConnectionState = {
    connected: false,
    reconnectAttempts: 0
  };
  private reconnectTimer?: NodeJS.Timeout;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000; // Start with 2 seconds
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || this.getDefaultBaseUrl();
  }

  private getDefaultBaseUrl(): string {
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
      const hostname = window.location.hostname;
      const port = hostname === 'localhost' ? '8000' : window.location.port;
      return `${protocol}//${hostname}:${port}`;
    }
    return 'http://localhost:8000';
  }

  /**
   * Connect to the real-time status stream
   */
  connect(): void {
    if (this.eventSource?.readyState === EventSource.OPEN) {
      console.log('Real-time status already connected');
      return;
    }

    const streamUrl = `${this.baseUrl}/status/stream`;
    console.log('Connecting to real-time status stream:', streamUrl);

    this.eventSource = new EventSource(streamUrl);

    this.eventSource.onopen = () => {
      console.log('Real-time status stream connected');
      this.updateConnectionState({ connected: true, reconnectAttempts: 0 });
      this.reconnectDelay = 2000; // Reset reconnect delay
    };

    this.eventSource.onmessage = (event) => {
      try {
        const statusEvent: RealTimeStatusEvent = JSON.parse(event.data);
        console.log('Status event received:', statusEvent);
        
        this.updateConnectionState({ connected: true, lastEvent: statusEvent });
        
        // Notify all subscribers
        this.subscribers.forEach(callback => {
          try {
            callback(statusEvent);
          } catch (error) {
            console.error('Error in status event subscriber:', error);
          }
        });
      } catch (error) {
        console.error('Error parsing status event:', error);
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('Status stream error:', error);
      this.updateConnectionState({ 
        connected: false, 
        error: 'Connection error',
        reconnectAttempts: this.connectionState.reconnectAttempts + 1
      });

      // Attempt to reconnect
      this.scheduleReconnect();
    };

    // Handle specific event types
    this.eventSource.addEventListener('connected', (event) => {
      console.log('Status stream connection confirmed');
    });

    this.eventSource.addEventListener('heartbeat', (event) => {
      // Heartbeat received, connection is alive
      this.updateConnectionState({ connected: true });
    });

    this.eventSource.addEventListener('status', (event) => {
      // Status events are handled in onmessage, but this ensures we catch them
      try {
        const statusEvent: RealTimeStatusEvent = JSON.parse(event.data);
        this.updateConnectionState({ connected: true, lastEvent: statusEvent });
      } catch (error) {
        console.error('Error parsing status event:', error);
      }
    });
  }

  /**
   * Disconnect from the status stream
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = undefined;
    }

    this.updateConnectionState({ connected: false, reconnectAttempts: 0 });
    console.log('Real-time status disconnected');
  }

  /**
   * Subscribe to status events
   */
  onStatusEvent(callback: (event: RealTimeStatusEvent) => void): () => void {
    this.subscribers.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.subscribers.delete(callback);
    };
  }

  /**
   * Subscribe to connection state changes
   */
  onConnectionChange(callback: (state: StatusConnectionState) => void): () => void {
    this.connectionSubscribers.add(callback);
    
    // Send current state immediately
    callback(this.connectionState);
    
    // Return unsubscribe function
    return () => {
      this.connectionSubscribers.delete(callback);
    };
  }

  /**
   * Get current connection state
   */
  getConnectionState(): StatusConnectionState {
    return { ...this.connectionState };
  }

  /**
   * Check if currently connected
   */
  isConnected(): boolean {
    return this.connectionState.connected && this.eventSource?.readyState === EventSource.OPEN;
  }

  /**
   * Fetch current status via REST API (fallback)
   */
  async getCurrentStatus(): Promise<RealTimeStatusEvent | null> {
    try {
      const response = await fetch(`${this.baseUrl}/status/current`, {
        headers: {
          'Accept': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data.current || null;
    } catch (error) {
      console.error('Error fetching current status:', error);
      return null;
    }
  }

  /**
   * Fetch status history via REST API
   */
  async getStatusHistory(limit: number = 50): Promise<RealTimeStatusEvent[]> {
    try {
      const response = await fetch(`${this.baseUrl}/status/history?limit=${limit}`, {
        headers: {
          'Accept': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data.history || [];
    } catch (error) {
      console.error('Error fetching status history:', error);
      return [];
    }
  }

  private updateConnectionState(updates: Partial<StatusConnectionState>): void {
    this.connectionState = { ...this.connectionState, ...updates };
    
    // Notify connection state subscribers
    this.connectionSubscribers.forEach(callback => {
      try {
        callback(this.connectionState);
      } catch (error) {
        console.error('Error in connection state subscriber:', error);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.connectionState.reconnectAttempts >= this.maxReconnectAttempts) {
      if (this.connectionState.reconnectAttempts >= this.maxReconnectAttempts) {
        console.log('Max reconnect attempts reached, giving up');
        this.updateConnectionState({ 
          error: 'Max reconnect attempts reached. Please refresh the page.' 
        });
      }
      return;
    }

    const delay = this.reconnectDelay * Math.pow(1.5, this.connectionState.reconnectAttempts);
    console.log(`Scheduling reconnect in ${delay}ms (attempt ${this.connectionState.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connect();
    }, Math.min(delay, 30000)); // Cap at 30 seconds
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    this.disconnect();
    this.subscribers.clear();
    this.connectionSubscribers.clear();
  }
}

// Singleton instance
export const realTimeStatusService = new RealTimeStatusService();
