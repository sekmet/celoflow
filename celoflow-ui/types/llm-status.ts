export type LLMStatus = 
  | 'thinking'     // Initial LLM processing
  | 'routing'      // Determining tools/actions
  | 'checking'     // Validating inputs/permissions  
  | 'finding'      // Searching for data
  | 'loading'      // Final response generation
  | 'swapping'     // Auto-swap in progress
  | 'transferring' // Transfer execution
  | 'checking_balance' // Balance verification
  | 'compliance_check' // KYC/compliance validation
  | 'tee_verification' // TEE attestation
  | 'kyc_check'    // KYC verification
  | 'route_finding' // Finding optimal swap routes
  | 'error'        // Failure state
  | 'idle';        // No active operation

export interface LLMStatusState {
  status: LLMStatus;
  message?: string;
  timestamp: number;
  operation?: string;
  // Real-time operation details
  amount?: string;
  token?: string;
  recipient?: string;
  transactionHash?: string;
  progress?: number; // 0.0 to 1.0
  error?: string;
  // Connection state for real-time updates
  realTimeEnabled?: boolean;
  connected?: boolean;
}

export interface StatusDetectionConfig {
  // Timing thresholds (ms) for heuristic-based detection
  thinkingThreshold: number;
  routingThreshold: number;
  checkingThreshold: number;
  findingThreshold: number;
  
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
      /(completed|done|finished|success)/i,
    ],
    swapping: [
      /(auto-swap|swap|exchange|convert|hop1|hop2)/i,
      /(swapping|exchanging|converting)/i,
      /([A-Z]{3,6}|c[A-Z]{2,4}|[a-z]{2,4})\s*[-→]\s*([A-Z]{3,6}|c[A-Z]{2,4}|[a-z]{2,4})/i,
      /(CELO.*USDm|USDm.*\w+)/i,
    ],
    transferring: [
      /(transfer|send|pay|remittance|payment)/i,
      /(ERC-20 transfer|transferring|sending)/i,
      /(tx:|transaction|broadcast)/i,
      /(transfer.*completed|sent.*successfully|payment.*successful)/i,
    ],
    checking_balance: [
      /(balance.*but needs|pre-flight balance)/i,
      /(check.*balance|verify.*balance)/i,
      /(insufficient|not enough)/i,
    ],
    compliance_check: [
      /(compliance|screening|sanction|aml)/i,
      /(compliance.*check|screening.*check)/i,
      /(risk.*assessment)/i,
    ],
    tee_verification: [
      /(tee|attestation|trusted execution)/i,
      /(tee.*verification|attestation.*check)/i,
      /(secure.*enclave)/i,
    ],
    kyc_check: [
      /(kyc|know your customer|identity)/i,
      /(kyc.*check|identity.*verification)/i,
      /(tier.*upgrade)/i,
    ],
    route_finding: [
      /(find.*route|optimal.*route|route.*optimization)/i,
      /(best.*path|efficient.*swap)/i,
      /(mento.*route)/i,
    ],
    error: [
      /(error|failed|unable|cannot|sorry|unfortunately)/i,
      /(issue|problem|trouble|difficulty|reverted)/i,
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
