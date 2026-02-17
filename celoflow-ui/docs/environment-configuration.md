# CeloFlow Environment Configuration Guide

## Overview

CeloFlow supports flexible blockchain configuration through environment variables, allowing you to easily switch between different Celo networks and custom RPC endpoints.

## Environment Variables

### Frontend Configuration (celoflow-ui/.env.local)

```bash
# API Configuration
VITE_CELOFLOW_API_URL=http://localhost:8000

# Blockchain Configuration
VITE_CELO_RPC_URL=https://forno.celo-sepolia.celo-testnet.org
VITE_CELO_CHAIN_ID=11142220
```

### Backend Configuration (celoflow/.env)

```bash
# Blockchain Configuration (Celo Sepolia Testnet)
CELO_RPC_URL=https://forno.celo-sepolia.celo-testnet.org
CHAIN_ID=11142220
```

## Supported Networks

### Celo Mainnet
```bash
VITE_CELO_RPC_URL=https://forno.celo.org
VITE_CELO_CHAIN_ID=42220
```

### Celo Sepolia Testnet
```bash
VITE_CELO_RPC_URL=https://forno.celo-sepolia.celo-testnet.org
VITE_CELO_CHAIN_ID=11142220
```

### Custom RPC Endpoints
You can use any compatible Celo RPC endpoint:

```bash
# Example with Alchemy
VITE_CELO_RPC_URL=https://celo-mainnet.g.alchemy.com/v2/YOUR_API_KEY
VITE_CELO_CHAIN_ID=42220

# Example with Ankr
VITE_CELO_RPC_URL=https://rpc.ankr.com/celo
VITE_CELO_CHAIN_ID=42220
```

## Configuration Details

### Frontend Configuration

The frontend uses the following configuration flow:

1. **wagmi-config.ts**: Reads environment variables and creates custom chain configuration
2. **useTokenBalances.ts**: Uses custom chain ID for balance queries
3. **WalletConnect.tsx**: Uses custom chain ID for balance display

### Backend Configuration

The backend uses environment variables for:

1. **Blockchain interaction**: Smart contract calls and transactions
2. **Agent operations**: On-chain transactions and validations
3. **Network detection**: Determining which network to operate on

## Implementation Details

### Custom Chain Configuration

When `VITE_CELO_RPC_URL` and `VITE_CELO_CHAIN_ID` are provided, the frontend creates a custom chain configuration:

```typescript
const customChain = {
  id: chainId,
  name: 'Celo Custom',
  nativeCurrency: {
    name: 'CELO',
    symbol: 'CELO',
    decimals: 18,
  },
  rpcUrls: {
    default: { http: [customRpcUrl] },
    public: { http: [customRpcUrl] },
  },
  blockExplorers: {
    default: {
      name: 'Celo Explorer',
      url: 'https://explorer.celo.org',
    },
  },
  testnet: chainId !== 42220,
}
```

### Fallback Logic

If no custom configuration is provided, the system falls back to:

1. **Frontend**: Default Celo Mainnet (42220) and Sepolia (44787) chains
2. **Backend**: Environment variables or hardcoded defaults

## Usage Examples

### Development Setup

1. Copy the example environment file:
```bash
cp celoflow-ui/.env.example celoflow-ui/.env.local
cp celoflow/.env.example celoflow/.env
```

2. Configure your desired network:
```bash
# For Celo Sepolia Testnet
echo "VITE_CELO_RPC_URL=https://forno.celo-sepolia.celo-testnet.org" >> celoflow-ui/.env.local
echo "VITE_CELO_CHAIN_ID=11142220" >> celoflow-ui/.env.local
```

3. Start the development servers:
```bash
# Backend
cd celoflow && python server.py

# Frontend
cd celoflow-ui && bun run dev
```

### Production Deployment

For production, set the environment variables in your deployment platform:

```bash
# Docker/Container
ENV VITE_CELO_RPC_URL=https://forno.celo.org
ENV VITE_CELO_CHAIN_ID=42220

# Cloud Platform (Vercel, Netlify, etc.)
VITE_CELO_RPC_URL=https://forno.celo.org
VITE_CELO_CHAIN_ID=42220
```

## Testing Configuration

To verify your configuration is working:

1. **Check console logs**: The system logs the RPC URL and chain ID being used
2. **Verify network detection**: Check that the wallet connects to the correct network
3. **Test balance fetching**: Ensure token balances are fetched from the correct network

## Troubleshooting

### Common Issues

1. **Chain ID Mismatch**: Ensure the chain ID matches the RPC endpoint
2. **RPC Connectivity**: Verify the RPC endpoint is accessible and working
3. **Wallet Connection**: Make sure your wallet is configured for the correct network

### Debug Logging

Enable debug logging to see configuration details:

```typescript
console.log('[wagmi-config] Using custom RPC:', customRpcUrl)
console.log('[wagmi-config] Using custom chain ID:', chainId)
console.log('[useTokenBalances] Using custom chain ID from env:', chainId)
```

## Security Considerations

1. **RPC Endpoints**: Use reputable RPC providers for production
2. **API Keys**: Never commit API keys to version control
3. **Environment Variables**: Use secure methods to manage environment variables in production

## Migration Guide

### From Default Configuration

1. Add environment variables to your `.env.local` file
2. Restart the development server
3. Verify the configuration in browser console logs

### From Hardcoded Configuration

1. Replace hardcoded RPC URLs with environment variables
2. Update chain ID references to use environment variables
3. Test with different networks to ensure flexibility

This configuration system provides maximum flexibility for deploying CeloFlow across different Celo networks and environments.
