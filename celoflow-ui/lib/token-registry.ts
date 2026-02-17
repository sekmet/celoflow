/**
 * Token Registry for CeloFlow Multi-Coin Wallet Display
 *
 * Comprehensive registry of all supported Celo stablecoins and tokens
 * with contract addresses for both Mainnet and Sepolia testnets.
 */

import { celo, celoAlfajores } from 'wagmi/chains'

export interface TokenInfo {
  symbol: string
  name: string
  decimals: number
  contractAddress: {
    mainnet: string
    sepolia: string
  }
  category: 'mento' | 'tether' | 'circle' | 'vnx' | 'mountain' | 'angle' | 'glo' | 'brla' | 'minteo' | 'gooddollar' | 'native'
  logoUrl?: string
  coingeckoId?: string
  description?: string
}

export const TOKEN_REGISTRY: Record<string, TokenInfo> = {
  // Native CELO
  CELO: {
    symbol: 'CELO',
    name: 'Celo Native Token',
    decimals: 18,
    contractAddress: {
      mainnet: '0x0000000000000000000000000000000000000000',
      sepolia: '0x0000000000000000000000000000000000000000'
    },
    category: 'native',
    description: 'Native governance and staking token of the Celo network'
  },

  // Mento Stablecoins
  USDm: {
    symbol: 'USDm',
    name: 'Mento Dollar',
    decimals: 18,
    contractAddress: {
      mainnet: '0x765de816845861e75a25fca122bb6898b8b1282a',
      sepolia: '0xdE9e4C3ce781b4bA68120d6261cbad65ce0aB00b'
    },
    category: 'mento',
    description: 'US Dollar-pegged stablecoin by Mento Labs'
  },
  EURm: {
    symbol: 'EURm',
    name: 'Mento Euro',
    decimals: 18,
    contractAddress: {
      mainnet: '0xd8763cba276a3738e6de85b4b3bf5fded6d6ca73',
      sepolia: '0xA99dC247d6b7B2E3ab48a1fEE101b83cD6aCd82a'
    },
    category: 'mento',
    description: 'Euro-pegged stablecoin by Mento Labs'
  },
  BRLm: {
    symbol: 'BRLm',
    name: 'Mento Brazilian Real',
    decimals: 18,
    contractAddress: {
      mainnet: '0xe8537a3d056da446677b9e9d6c5db704eaab4787',
      sepolia: '0x2294298942fdc79417DE9E0D740A4957E0e7783a'
    },
    category: 'mento',
    description: 'Brazilian Real-pegged stablecoin by Mento Labs'
  },
  XOFm: {
    symbol: 'XOFm',
    name: 'Mento West African CFA Franc',
    decimals: 18,
    contractAddress: {
      mainnet: '0x73F93dcc49cB8A239e2032663e9475dd5ef29A08',
      sepolia: '0x5505b70207aE3B826c1A7607F19F3Bf73444A082'
    },
    category: 'mento',
    description: 'West African CFA Franc-pegged stablecoin by Mento Labs'
  },
  KESm: {
    symbol: 'KESm',
    name: 'Mento Kenyan Shilling',
    decimals: 18,
    contractAddress: {
      mainnet: '0x456a3D042C0DbD3db53D5489e98dFb038553B0d0',
      sepolia: '0xC7e4635651E3e3Af82b61d3E23c159438daE3BbF'
    },
    category: 'mento',
    description: 'Kenyan Shilling-pegged stablecoin by Mento Labs'
  },
  PHPm: {
    symbol: 'PHPm',
    name: 'Mento Philippine Peso',
    decimals: 18,
    contractAddress: {
      mainnet: '0x105d4A9306D2E55a71d2Eb95B81553AE1dC20d7B',
      sepolia: '0x0352976d940a2C3FBa0C3623198947Ee1d17869E'
    },
    category: 'mento',
    description: 'Philippine Peso-pegged stablecoin by Mento Labs'
  },
  COPm: {
    symbol: 'COPm',
    name: 'Mento Colombian Peso',
    decimals: 18,
    contractAddress: {
      mainnet: '0x8a567e2ae79ca692bd748ab832081c45de4041ea',
      sepolia: '0x5F8d55c3627d2dc0a2B4afa798f877242F382F67'
    },
    category: 'mento',
    description: 'Colombian Peso-pegged stablecoin by Mento Labs'
  },
  GBPm: {
    symbol: 'GBPm',
    name: 'Mento British Pound',
    decimals: 18,
    contractAddress: {
      mainnet: '0xCCF663b1fF11028f0b19058d0f7B674004a40746',
      sepolia: '0x85F5181Abdbf0e1814Fc4358582Ae07b8eBA3aF3'
    },
    category: 'mento',
    description: 'British Pound-pegged stablecoin by Mento Labs'
  },
  CADm: {
    symbol: 'CADm',
    name: 'Mento Canadian Dollar',
    decimals: 18,
    contractAddress: {
      mainnet: '0xff4Ab19391af240c311c54200a492233052B6325',
      sepolia: '0xF151c9a13b78C84f93f50B8b3bC689fedc134F60'
    },
    category: 'mento',
    description: 'Canadian Dollar-pegged stablecoin by Mento Labs'
  },
  AUDm: {
    symbol: 'AUDm',
    name: 'Mento Australian Dollar',
    decimals: 18,
    contractAddress: {
      mainnet: '0x7175504C455076F15c04A2F90a8e352281F492F9',
      sepolia: '0x5873Faeb42F3563dcD77F0fbbdA818E6d6DA3139'
    },
    category: 'mento',
    description: 'Australian Dollar-pegged stablecoin by Mento Labs'
  },
  ZARm: {
    symbol: 'ZARm',
    name: 'Mento South African Rand',
    decimals: 18,
    contractAddress: {
      mainnet: '0x4c35853A3B4e647fD266f4de678dCc8fEC410BF6',
      sepolia: '0x10CCfB235b0E1Ed394bACE4560C3ed016697687e'
    },
    category: 'mento',
    description: 'South African Rand-pegged stablecoin by Mento Labs'
  },
  GHSm: {
    symbol: 'GHSm',
    name: 'Mento Ghanaian Cedi',
    decimals: 18,
    contractAddress: {
      mainnet: '0xfAeA5F3404bbA20D3cc2f8C4B0A888F55a3c7313',
      sepolia: '0x5e94B8C872bD47BC4255E60ECBF44D5E66e7401C'
    },
    category: 'mento',
    description: 'Ghanaian Cedi-pegged stablecoin by Mento Labs'
  },
  NGNm: {
    symbol: 'NGNm',
    name: 'Mento Nigerian Naira',
    decimals: 18,
    contractAddress: {
      mainnet: '0xE2702Bd97ee33c88c8f6f92DA3B733608aa76F71',
      sepolia: '0x3d5ae86F34E2a82771496D140daFAEf3789dF888'
    },
    category: 'mento',
    description: 'Nigerian Naira-pegged stablecoin by Mento Labs'
  },
  JPYm: {
    symbol: 'JPYm',
    name: 'Mento Japanese Yen',
    decimals: 18,
    contractAddress: {
      mainnet: '0xc45eCF20f3CD864B32D9794d6f76814aE8892e20',
      sepolia: '0x85Bee67D435A39f7467a8a9DE34a5B73D25Df426'
    },
    category: 'mento',
    description: 'Japanese Yen-pegged stablecoin by Mento Labs'
  },
  CHFm: {
    symbol: 'CHFm',
    name: 'Mento Swiss Franc',
    decimals: 18,
    contractAddress: {
      mainnet: '0xb55a79F398E759E43C95b979163f30eC87Ee131D',
      sepolia: '0x284E9b7B623eAE866914b7FA0eB720C2Bb3C2980'
    },
    category: 'mento',
    description: 'Swiss Franc-pegged stablecoin by Mento Labs'
  },

  // Tether
  USDT: {
    symbol: 'USDT',
    name: 'Tether USD',
    decimals: 6,
    contractAddress: {
      mainnet: '0x48065fbbe25f71c9282ddf5e1cd6d6a887483d5e',
      sepolia: '0xd077A400968890Eacc75cdc901F0356c943e4fDb'
    },
    category: 'tether',
    description: 'Popular USD-pegged stablecoin by Tether'
  },

  // Circle
  USDC: {
    symbol: 'USDC',
    name: 'USD Coin',
    decimals: 6,
    contractAddress: {
      mainnet: '0xceba9300f2b948710d2653dd7b07f33a8b32118c',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'circle',
    description: 'Widely used USD-pegged stablecoin by Circle'
  },

  // VNX Stablecoins
  vEUR: {
    symbol: 'vEUR',
    name: 'VNX Euro',
    decimals: 18,
    contractAddress: {
      mainnet: '0x9346f43c1588b6df1d52bdd6bf846064f92d9cba',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'vnx',
    description: 'Euro-pegged stablecoin by VNX'
  },
  vGBP: {
    symbol: 'vGBP',
    name: 'VNX British Pound',
    decimals: 18,
    contractAddress: {
      mainnet: '0x7ae4265ecfc1f31bc0e112dfcfe3d78e01f4bb7f',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'vnx',
    description: 'British Pound-pegged stablecoin by VNX'
  },
  vCHF: {
    symbol: 'vCHF',
    name: 'VNX Swiss Franc',
    decimals: 18,
    contractAddress: {
      mainnet: '0xc5ebea9984c485ec5d58ca5a2d376620d93af871',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'vnx',
    description: 'Swiss Franc-pegged stablecoin by VNX'
  },

  // Mountain Protocol
  USDM: {
    symbol: 'USDM',
    name: 'Mountain USD',
    decimals: 18,
    contractAddress: {
      mainnet: '0x59D9356E565Ab3A36dD77763Fc0d87fEaf85508C',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'mountain',
    description: 'Yield-bearing USD stablecoin by Mountain Protocol'
  },

  // Angle Protocol
  USDA: {
    symbol: 'USDA',
    name: 'Angle USD',
    decimals: 18,
    contractAddress: {
      mainnet: '0x0000206329b97DB379d5E1Bf586BbDB969C63274',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'angle',
    description: 'Yield-bearing USD stablecoin by Angle Protocol'
  },
  EURA: {
    symbol: 'EURA',
    name: 'Angle Euro',
    decimals: 18,
    contractAddress: {
      mainnet: '0xC16B81Af351BA9e64C1a069E3Ab18c244A1E3049',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'angle',
    description: 'Yield-bearing Euro stablecoin by Angle Protocol'
  },

  // Glo Foundation
  USDGLO: {
    symbol: 'USDGLO',
    name: 'Glo Dollar',
    decimals: 18,
    contractAddress: {
      mainnet: '0x4f604735c1cf31399c6e711d5962b2b3e0225ad3',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'glo',
    description: 'Impact-driven USD stablecoin supporting global causes'
  },

  // BRLA Digital
  BRLA: {
    symbol: 'BRLA',
    name: 'BRLA Digital',
    decimals: 2,
    contractAddress: {
      mainnet: '0xfecb3f7c54e2caae9dc6ac9060a822d47e053760',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'brla',
    description: 'Brazil-based stablecoin by BRLA Digital'
  },

  // Minteo
  COPM: {
    symbol: 'COPM',
    name: 'Minteo Colombian Peso',
    decimals: 2,
    contractAddress: {
      mainnet: '0xC92E8Fc2947E32F2B574CCA9F2F12097A71d5606',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'minteo',
    description: 'Fiat-backed Colombian Peso Stablecoin by Minteo'
  },

  // GoodDollar
  G_DOLLAR: {
    symbol: 'G$',
    name: 'GoodDollar',
    decimals: 18,
    contractAddress: {
      mainnet: '0x62b8b11039fcfe5ab0c56e502b1c372a3d2a9c7a',
      sepolia: '0x0000000000000000000000000000000000000000' // Not deployed on Sepolia
    },
    category: 'gooddollar',
    description: 'UBI-focused stablecoin for financial inclusion'
  }
}

/**
 * Get token contract address for specific network
 */
export function getTokenContractAddress(tokenSymbol: string, chainId: number): string {
  const token = TOKEN_REGISTRY[tokenSymbol]
  if (!token) {
    throw new Error(`Token ${tokenSymbol} not found in registry`)
  }

  if (chainId === celo.id) {
    return token.contractAddress.mainnet
  } else if (chainId === celoAlfajores.id) {
    return token.contractAddress.sepolia
  } else {
    throw new Error(`Unsupported chain ID: ${chainId}`)
  }
}

/**
 * Get all tokens for a specific category
 */
export function getTokensByCategory(category: TokenInfo['category']): TokenInfo[] {
  return Object.values(TOKEN_REGISTRY).filter(token => token.category === category)
}

/**
 * Get all tokens available on a specific network
 */
export function getTokensForNetwork(chainId: number): TokenInfo[] {
  return Object.values(TOKEN_REGISTRY).filter(token => {
    try {
      const address = getTokenContractAddress(token.symbol, chainId)
      // Native tokens use zero address, so include them by category
      if (token.category === 'native') {
        return true
      }
      return address !== '0x0000000000000000000000000000000000000000'
    } catch {
      return false
    }
  })
}

/**
 * Get priority tokens for display (top tokens by usage and importance)
 */
export function getPriorityTokens(): string[] {
  return [
    'CELO',     // Native token
    'USDm',     // Mento Dollar
    'USDC',     // Circle USDC
    'USDT',     // Tether
    'EURm',     // Mento Euro
    'cUSD',     // Legacy Celo Dollar (if still supported)
    'cEUR',     // Legacy Celo Euro (if still supported)
    'BRLm',     // Brazilian Real
    'PHPm',     // Philippine Peso
    'KESm'      // Kenyan Shilling
  ]
}

/**
 * Check if a token is a stablecoin (price-pegged)
 */
export function isStablecoin(tokenSymbol: string): boolean {
  const token = TOKEN_REGISTRY[tokenSymbol]
  return token ? token.category !== 'native' : false
}

/**
 * Get token display priority for sorting
 */
export function getTokenPriority(tokenSymbol: string): number {
  const priorityTokens = getPriorityTokens()
  const index = priorityTokens.indexOf(tokenSymbol)
  return index === -1 ? 999 : index
}
