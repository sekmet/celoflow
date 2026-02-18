import { LLMStatus, LLMStatusState, StatusDetectionConfig, DEFAULT_STATUS_CONFIG } from '../types/llm-status';
import { realTimeStatusService, RealTimeStatusEvent } from '../services/real-time-status';

export class LLMStatusDetector {
  private startTime: number = 0;
  private lastStatus: LLMStatus = 'idle';
  private statusHistory: LLMStatusState[] = [];
  private config: StatusDetectionConfig;
  private timer: NodeJS.Timeout | null = null;
  private statusCallback?: ((status: LLMStatusState) => void) | null = null;
  private realTimeEnabled: boolean = true;
  private realTimeUnsubscribe?: () => void;
  private connectionUnsubscribe?: () => void;
  private isRealTimeConnected: boolean = false;

  constructor(config: Partial<StatusDetectionConfig> = {}) {
    this.config = { ...DEFAULT_STATUS_CONFIG, ...config };
    this.setupRealTimeStatus();
  }

  /**
   * Setup real-time status monitoring
   */
  private setupRealTimeStatus(): void {
    if (!this.realTimeEnabled) return;

    // Subscribe to real-time status events
    this.realTimeUnsubscribe = realTimeStatusService.onStatusEvent((event: RealTimeStatusEvent) => {
      this.handleRealTimeStatusEvent(event);
    });

    // Subscribe to connection state changes
    this.connectionUnsubscribe = realTimeStatusService.onConnectionChange((state) => {
      this.isRealTimeConnected = state.connected;
      
      // Update current status with connection info
      const currentStatus = this.createStatusState(this.lastStatus);
      currentStatus.connected = state.connected;
      currentStatus.realTimeEnabled = this.realTimeEnabled;
      
      if (state.error) {
        currentStatus.error = state.error;
      }
      
      // Emit status update to show connection state
      if (this.statusCallback) {
        this.statusCallback(currentStatus);
      }
    });

    // Connect to real-time status stream
    try {
      realTimeStatusService.connect();
    } catch (error) {
      console.warn('Failed to connect to real-time status:', error);
      this.realTimeEnabled = false;
    }
  }

  /**
   * Handle real-time status events from backend
   */
  private handleRealTimeStatusEvent(event: RealTimeStatusEvent): void {
    // Map backend operation to frontend status
    const status = this.mapOperationToStatus(event.operation);
    
    if (status !== this.lastStatus) {
      this.lastStatus = status;
      
      const statusState = this.createStatusState(status, event);
      this.statusHistory.push(statusState);
      
      console.log('Real-time status update:', statusState);
      
      // Emit status update
      if (this.statusCallback) {
        this.statusCallback(statusState);
      }
    }
  }

  /**
   * Map backend operation type to frontend LLM status
   */
  private mapOperationToStatus(operation: string): LLMStatus {
    const operationMap: Record<string, LLMStatus> = {
      'swapping': 'swapping',
      'transferring': 'transferring',
      'checking_balance': 'checking_balance',
      'compliance_check': 'compliance_check',
      'tee_verification': 'tee_verification',
      'kyc_check': 'kyc_check',
      'route_finding': 'route_finding',
      'error': 'error',
      'idle': 'idle',
    };
    
    return operationMap[operation] || 'loading';
  }

  /**
   * Create status state with real-time details
   */
  private createStatusState(status: LLMStatus, event?: RealTimeStatusEvent): LLMStatusState {
    const statusState: LLMStatusState = {
      status,
      timestamp: Date.now(),
      realTimeEnabled: this.realTimeEnabled,
      connected: this.isRealTimeConnected,
    };

    if (event) {
      statusState.message = event.message;
      statusState.operation = event.operation;
      statusState.amount = event.amount;
      statusState.token = event.token;
      statusState.recipient = event.recipient;
      statusState.transactionHash = event.transaction_hash;
      statusState.progress = event.progress;
      statusState.error = event.details?.error_message;
    }

    return statusState;
  }

  /**
   * Start monitoring a new streaming session
   */
  start(onStatus?: (status: LLMStatusState) => void): void {
    this.startTime = Date.now();
    this.lastStatus = 'idle';
    this.statusHistory = [];
    this.statusCallback = onStatus || null;
    
    // Start periodic status updates based on timing (fallback)
    this.startPeriodicUpdates();
    
    // Try to get current status from backend
    this.fetchCurrentStatus();
  }

  /**
   * Fetch current status from backend REST API
   */
  private async fetchCurrentStatus(): Promise<void> {
    if (!this.realTimeEnabled) return;
    
    try {
      const currentStatus = await realTimeStatusService.getCurrentStatus();
      if (currentStatus) {
        this.handleRealTimeStatusEvent(currentStatus);
      }
    } catch (error) {
      console.warn('Failed to fetch current status:', error);
    }
  }

  /**
   * Start periodic updates for timing-based status progression (fallback)
   */
  private startPeriodicUpdates(): void {
    if (this.timer) clearInterval(this.timer);
    
    this.timer = setInterval(() => {
      // Skip if real-time is connected and active
      if (this.isRealTimeConnected && this.realTimeEnabled) {
        return;
      }
      
      const elapsed = Date.now() - this.startTime;
      const heuristicStatus = this.detectStatusFromTiming(elapsed);
      
      if (heuristicStatus !== this.lastStatus) {
        this.lastStatus = heuristicStatus;
        const statusState = this.createStatusState(heuristicStatus);
        this.statusHistory.push(statusState);
        console.log('Fallback status update:', statusState);
        
        // Emit status update if callback is provided
        if (this.statusCallback) {
          this.statusCallback(statusState);
        }
      }
    }, 500); // Check every 500ms
  }

  /**
   * Stop monitoring and clean up timer and subscriptions
   */
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    
    // Clean up real-time subscriptions
    if (this.realTimeUnsubscribe) {
      this.realTimeUnsubscribe();
      this.realTimeUnsubscribe = undefined;
    }
    
    if (this.connectionUnsubscribe) {
      this.connectionUnsubscribe();
      this.connectionUnsubscribe = undefined;
    }
    
    // Disconnect from real-time status
    if (this.realTimeEnabled) {
      realTimeStatusService.disconnect();
    }
  }

  /**
   * Analyze streaming content and determine current status
   */
  analyzeContent(content: string): LLMStatusState {
    const elapsed = Date.now() - this.startTime;
    const detectedStatus = this.detectStatusFromContent(content);
    const heuristicStatus = this.detectStatusFromTiming(elapsed);
    
    console.log('Status analysis:', { content, elapsed, detectedStatus, heuristicStatus });
    
    // Prioritize real-time status if connected and actively receiving events,
    // then content-based detection, then timing heuristics
    let status: LLMStatus;
    if (this.isRealTimeConnected && this.realTimeEnabled && detectedStatus !== 'idle') {
      // Real-time is connected AND content detected a meaningful operation
      status = detectedStatus;
    } else if (this.isRealTimeConnected && this.realTimeEnabled) {
      // Real-time is connected but no meaningful content detected
      status = this.lastStatus; // Keep current real-time status
    } else {
      // Real-time not connected, use content or timing heuristics
      status = detectedStatus !== 'idle' ? detectedStatus : heuristicStatus;
    }
    
    const operation = this.detectOperation(content);
    
    // Update if status changed or if content detected a new meaningful operation
    const shouldUpdate = status !== this.lastStatus || 
                        (detectedStatus !== 'idle' && detectedStatus !== this.lastStatus && this.isRealTimeConnected);
    
    if (shouldUpdate) {
      this.lastStatus = status;
      const statusState = this.createStatusState(status);
      statusState.operation = operation;
      this.statusHistory.push(statusState);
      console.log('Status changed to:', statusState);
      return statusState;
    }
    
    return this.createStatusState(this.lastStatus);
  }
  
  /**
   * Detect status from content patterns
   */
  private detectStatusFromContent(content: string): LLMStatus {
    const normalizedContent = content.toLowerCase().trim();
    
    // Check status patterns in priority order
    for (const [status, patterns] of Object.entries(this.config.statusPatterns)) {
      if (status === 'idle') continue;
      
      for (const pattern of patterns) {
        if (pattern.test(normalizedContent)) {
          return status as LLMStatus;
        }
      }
    }
    
    return 'idle';
  }
  
  /**
   * Detect status from timing heuristics
   */
  private detectStatusFromTiming(elapsed: number): LLMStatus {
    if (elapsed < this.config.thinkingThreshold) {
      return 'thinking';
    } else if (elapsed < this.config.routingThreshold) {
      return 'routing';
    } else if (elapsed < this.config.checkingThreshold) {
      return 'checking';
    } else if (elapsed < this.config.findingThreshold) {
      return 'finding';
    } else {
      return 'loading';
    }
  }
  
  /**
   * Detect the type of operation being performed
   */
  private detectOperation(content: string): string | undefined {
    const normalizedContent = content.toLowerCase();
    
    for (const [operation, keywords] of Object.entries(this.config.operationKeywords)) {
      for (const keyword of keywords) {
        if (normalizedContent.includes(keyword)) {
          return operation;
        }
      }
    }
    
    return undefined;
  }
  
  /**
   * Get status history for debugging
   */
  getHistory(): LLMStatusState[] {
    return [...this.statusHistory];
  }
  
  /**
   * Reset detector state
   */
  reset(): void {
    this.stop(); // Stop the timer and clean up subscriptions
    this.startTime = 0;
    this.lastStatus = 'idle';
    this.statusHistory = [];
    this.isRealTimeConnected = false;
    
    // Restart real-time monitoring if enabled
    if (this.realTimeEnabled) {
      this.setupRealTimeStatus();
    }
  }
  
  /**
   * Get current status
   */
  getCurrentStatus(): LLMStatus {
    return this.lastStatus;
  }
  
  /**
   * Get connection state
   */
  getConnectionState(): { realTimeEnabled: boolean; connected: boolean } {
    return {
      realTimeEnabled: this.realTimeEnabled,
      connected: this.isRealTimeConnected,
    };
  }
  
  /**
   * Enable or disable real-time status
   */
  setRealTimeEnabled(enabled: boolean): void {
    if (this.realTimeEnabled === enabled) return;
    
    this.realTimeEnabled = enabled;
    
    if (enabled) {
      this.setupRealTimeStatus();
    } else {
      this.stop();
      this.realTimeUnsubscribe = undefined;
      this.connectionUnsubscribe = undefined;
      realTimeStatusService.disconnect();
      this.isRealTimeConnected = false;
    }
  }
}
