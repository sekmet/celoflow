export const SUGGESTED_PROMPTS = [
  "Send 50 cUSD to Mom in Philippines",
  "Transfer 200 EUR to Juan in Mexico",
  "Pay landlord 15000 KES via M-Pesa",
  "Send 100 cUSD to Dad every month",
];

export const NAV_LINKS = [
  { name: 'How it Works', href: '#how-it-works' },
  { name: 'Features', href: '#features' },
  { name: 'Developers', href: '#developers' },
];

export const SUPPORTED_CURRENCIES = [
  // Native token
  'CELO',
  
  // Mento Stablecoins
  'USDm', 'EURm', 'BRLm', 'XOFm', 'KESm', 'PHPm', 'COPm', 'GBPm', 
  'CADm', 'AUDm', 'ZARm', 'GHSm', 'NGNm', 'JPYm', 'CHFm',
  
  // Major stablecoins
  'USDC', 'USDT',
  
  // VNX Stablecoins
  'vEUR', 'vGBP', 'vCHF',
  
  // Yield-bearing stablecoins
  'USDM', 'USDA', 'EURA',
  
  // Other stablecoins
  'USDGLO', 'BRLA', 'COPM', 'G$',
  
  // Legacy Celo tokens (for backward compatibility)
  'cUSD', 'cEUR',
  
  // Traditional currencies for display
  'USD', 'EUR', 'GBP', 'JPY', 'BRL', 'PHP', 'MXN', 'KES'
];

// Token categories for grouping and filtering
export const TOKEN_CATEGORIES = {
  native: ['CELO'],
  mento: ['USDm', 'EURm', 'BRLm', 'XOFm', 'KESm', 'PHPm', 'COPm', 'GBPm', 'CADm', 'AUDm', 'ZARm', 'GHSm', 'NGNm', 'JPYm', 'CHFm'],
  tether: ['USDT'],
  circle: ['USDC'],
  vnx: ['vEUR', 'vGBP', 'vCHF'],
  mountain: ['USDM'],
  angle: ['USDA', 'EURA'],
  glo: ['USDGLO'],
  brla: ['BRLA'],
  minteo: ['COPM'],
  gooddollar: ['G$'],
  legacy: ['cUSD', 'cEUR']
} as const;

// Priority tokens for display ordering
export const PRIORITY_TOKENS = [
  'CELO',     // Native token - highest priority
  'USDm',     // Mento Dollar
  'USDC',     // Circle USDC
  'USDT',     // Tether
  'EURm',     // Mento Euro
  'cUSD',     // Legacy Celo Dollar
  'cEUR',     // Legacy Celo Euro
  'BRLm',     // Brazilian Real
  'PHPm',     // Philippine Peso
  'KESm'      // Kenyan Shilling
];

// Token display priorities (lower number = higher priority)
export const TOKEN_DISPLAY_PRIORITY: Record<string, number> = {
  'CELO': 1,
  'USDm': 2,
  'USDC': 3,
  'USDT': 4,
  'EURm': 5,
  'cUSD': 6,
  'cEUR': 7,
  'BRLm': 8,
  'PHPm': 9,
  'KESm': 10,
  // All other tokens get priority 999
} as const;