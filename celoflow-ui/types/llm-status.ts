export type LLMStatus = 
  | 'thinking'     // Initial LLM processing
  | 'routing'      // Determining tools/actions
  | 'checking'     // Validating inputs/permissions  
  | 'finding'      // Searching for data
  | 'loading'      // Final response generation
  | 'error'        // Failure state
  | 'idle';        // No active operation

export interface LLMStatusState {
  status: LLMStatus;
  message?: string;
  timestamp: number;
  operation?: string;
}

export interface StatusDetectionConfig {
  // Timing thresholds (ms) for heuristic-based detection
  thinkingThreshold: number;
  routingThreshold: number;
  checkingThreshold: number;
  findingThreshold: number;
  
  // Content patterns for status detection
  statusPatterns: Record<LLMStatus, RegExp[]>;
  
  // Operation keywords for context
  operationKeywords: {
    transfer: string[];
    swap: string[];
    balance: string[];
    contact: string[];
    rate: string[];
  };
}

export const DEFAULT_STATUS_CONFIG: StatusDetectionConfig = {
  thinkingThreshold: 500,     // Reduced from 1000ms
  routingThreshold: 1500,     // Reduced from 2000ms
  checkingThreshold: 2500,    // Reduced from 3500ms
  findingThreshold: 4000,     // Reduced from 5000ms
  
  statusPatterns: {
    thinking: [
      /^(let me|i need to|i'll|i will|checking|analyzing|understanding|okay|alright|sure)/i,
      /(thinking|processing|considering|let me see|i can help)/i,
      /(i'll check|i will check|i can check)/i,
    ],
    routing: [
      /(route|routing|determine|decide|choose|select|best way)/i,
      /(which tool|what tool|using|leveraging|best method)/i,
      /(optimal route|best route|efficient way)/i,
    ],
    checking: [
      /(check|verify|validate|confirm|ensure|review)/i,
      /(permission|balance|wallet|address|funds)/i,
      /(let me verify|i need to check|checking if)/i,
    ],
    finding: [
      /(find|search|lookup|get|fetch|retrieve|looking for)/i,
      /(contact|rate|price|data|information|details)/i,
      /(getting|fetching|retrieving|searching for)/i,
    ],
    loading: [
      /(loading|generating|preparing|creating|building)/i,
      /(almost|just|nearly|almost done|ready)/i,
      /(finalizing|completing|finishing up)/i,
    ],
    error: [
      /(error|failed|unable|cannot|sorry|unfortunately)/i,
      /(issue|problem|trouble|difficulty)/i,
    ],
    idle: [],
  },
  
  operationKeywords: {
    transfer: ['send', 'transfer', 'pay', 'remittance', 'payment'],
    swap: ['swap', 'exchange', 'convert', 'trade'],
    balance: ['balance', 'holdings', 'portfolio', 'funds'],
    contact: ['contact', 'recipient', 'receiver', 'person'],
    rate: ['rate', 'price', 'cost', 'fee', 'exchange'],
  },
};
