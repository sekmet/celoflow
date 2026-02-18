import { LLMStatus, LLMStatusState, StatusDetectionConfig, DEFAULT_STATUS_CONFIG } from '../types/llm-status';

export class LLMStatusDetector {
  private startTime: number = 0;
  private lastStatus: LLMStatus = 'idle';
  private statusHistory: LLMStatusState[] = [];
  private config: StatusDetectionConfig;
  private timer: NodeJS.Timeout | null = null;
  private statusCallback?: ((status: LLMStatusState) => void) | null = null;

  constructor(config: Partial<StatusDetectionConfig> = {}) {
    this.config = { ...DEFAULT_STATUS_CONFIG, ...config };
  }

  /**
   * Start monitoring a new streaming session
   */
  start(onStatus?: (status: LLMStatusState) => void): void {
    this.startTime = Date.now();
    this.lastStatus = 'idle';
    this.statusHistory = [];
    this.statusCallback = onStatus || null;
    
    // Start periodic status updates based on timing
    this.startPeriodicUpdates();
  }

  /**
   * Start periodic updates for timing-based status progression
   */
  private startPeriodicUpdates(): void {
    if (this.timer) clearInterval(this.timer);
    
    this.timer = setInterval(() => {
      const elapsed = Date.now() - this.startTime;
      const heuristicStatus = this.detectStatusFromTiming(elapsed);
      
      if (heuristicStatus !== this.lastStatus) {
        this.lastStatus = heuristicStatus;
        const statusState: LLMStatusState = {
          status: heuristicStatus,
          timestamp: Date.now(),
        };
        this.statusHistory.push(statusState);
        console.log('Periodic status update:', statusState);
        
        // Emit status update if callback is provided
        if (this.statusCallback) {
          this.statusCallback(statusState);
        }
      }
    }, 500); // Check every 500ms
  }

  /**
   * Stop monitoring and clean up timer
   */
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
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
    
    // Prioritize content-based detection over timing heuristics
    const status = detectedStatus !== 'idle' ? detectedStatus : heuristicStatus;
    const operation = this.detectOperation(content);
    
    // Always update if timing heuristics suggest a different status
    const shouldUpdate = status !== this.lastStatus || 
                        (detectedStatus === 'idle' && heuristicStatus !== this.lastStatus);
    
    if (shouldUpdate) {
      this.lastStatus = status;
      const statusState: LLMStatusState = {
        status,
        timestamp: Date.now(),
        operation,
      };
      this.statusHistory.push(statusState);
      console.log('Status changed to:', statusState);
      return statusState;
    }
    
    return { status: this.lastStatus, timestamp: Date.now(), operation };
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
    this.stop(); // Stop the timer
    this.startTime = 0;
    this.lastStatus = 'idle';
    this.statusHistory = [];
  }
  
  /**
   * Get current status
   */
  getCurrentStatus(): LLMStatus {
    return this.lastStatus;
  }
}
