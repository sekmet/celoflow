# ERC-8004 Remittance Agent Smart Contracts

Production-ready smart contracts for the ERC-8004 Remittance Agent infrastructure on Celo.

## Overview

This repository contains the core smart contracts for implementing ERC-8004 agents with TEE attestation support, specifically designed for the Remittance Intent Agent use case.

## Contracts

### Core Contracts

- **IdentityRegistry.sol** - ERC-721 based agent identity registry with metadata support
- **TEERegistry.sol** - TEE attestation management for secure agent operations  
- **ReputationRegistry.sol** - Feedback system for agent reputation tracking

### Key Features

✅ **ERC-8004 Compliant** - Full implementation of the ERC-8004 specification  
✅ **TEE Integration** - Support for Intel TDX and SEV-SNP attestations  
✅ **Production Ready** - Extensive testing, access controls, and security patterns  
✅ **Celo Optimized** - Designed for Celo's mobile-first ecosystem  
✅ **Gas Efficient** - Optimized for low-cost transactions  

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Identity       │    │  Reputation     │    │  TEE            │
│  Registry       │◄──►│  Registry       │◄──►│  Registry       │
│  (ERC-721)      │    │  (Feedback)     │    │  (Attestation)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Agent          │
                    │  Operations     │
                    └─────────────────┘
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd contracts

# Install dependencies
forge install

# Install OpenZeppelin contracts
forge install OpenZeppelin/openzeppelin-contracts --no-commit

# Install forge-std
forge install foundry-rs/forge-std --no-commit
```

## Usage

### Deployment

Deploy to Celo Sepolia Testnet:

```bash
# Set environment variables
export PRIVATE_KEY=your_private_key
export CELO_SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/your_project_id
export CELOSCAN_API_KEY=your_celoscan_api_key

# Deploy contracts
forge script script/Deploy.s.sol --rpc-url $CELO_SEPOLIA_RPC_URL --private-key $PRIVATE_KEY --broadcast --verify
```

### Local Development

```bash
# Start local Anvil node
anvil --chain-id 44787

# Run tests
forge test

# Run specific test
forge test --match-test test_RegisterWithMetadata

# Run with gas tracking
forge test --gas-report
```

## Contract Details

### IdentityRegistry

ERC-721 based registry for agent identities with:

- **Agent Registration** - Mint NFTs representing agent identities
- **Metadata Storage** - Arbitrary key-value metadata for agents
- **URI Management** - IPFS/HTTP links to agent manifests
- **Wallet Management** - Agent wallet addresses for TEE operations

```solidity
// Register a new agent
uint256 agentId = identityRegistry.register(
    "ipfs://QmAgentMetadata",
    metadata
);

// Set agent wallet for TEE operations
identityRegistry.setAgentWallet(agentId, teeWallet);
```

### TEERegistry

Manages TEE attestations and public keys:

- **Verifier Management** - Whitelist TEE verifiers (Automata DCAP, etc.)
- **Key Registration** - Register TEE-derived public keys with attestations
- **Attestation Validation** - Verify TEE proof authenticity
- **Agent Binding** - Link TEE keys to agent identities

```solidity
// Add TEE verifier
teeRegistry.addVerifier(dcapVerifier, keccak256("TDX"));

// Register TEE key with attestation
teeRegistry.addKey(
    agentId,
    keccak256("TDX"),
    codeMeasurement,
    teePublicKey,
    "ipfs://QmCodeConfig",
    dcapVerifier,
    attestationProof
);
```

### ReputationRegistry

Feedback system for agent reputation:

- **Feedback Submission** - Submit structured feedback with scores
- **Reputation Calculation** - Aggregate feedback into reputation scores
- **Tag-based Filtering** - Filter feedback by categories
- **Revocation Support** - Allow clients to revoke feedback

```solidity
// Submit feedback for agent
reputationRegistry.giveFeedback(
    agentId,
    85,        // Score (0-100)
    0,         // Decimals
    "performance", // Primary tag
    "reliability", // Secondary tag
    "endpoint",
    "ipfs://QmFeedback",
    keccak256("feedback")
);

// Get reputation summary
(uint64 count, int128 avgScore, uint8 decimals) = 
    reputationRegistry.getSummary(agentId, clients, "performance", "");
```

## Testing

The contracts include comprehensive test suites:

```bash
# Run all tests
forge test

# Run specific contract tests
forge test --match-contract IdentityRegistry
forge test --match-contract TEERegistry  
forge test --match-contract ReputationRegistry

# Run with coverage
forge coverage

# Run fuzz tests
forge test --fuzz-runs 1000
```

### Test Coverage

- ✅ Unit tests for all public functions
- ✅ Revert tests for all error conditions
- ✅ Access control tests
- ✅ Fuzz testing for edge cases
- ✅ Integration tests between contracts

## Security

### Security Features

- **Reentrancy Protection** - All external functions protected
- **Access Control** - Owner/operator/approved patterns
- **Input Validation** - Comprehensive parameter validation
- **Error Handling** - Custom error types for clarity

### Audits

This codebase is designed following security best practices and includes:

- OpenZeppelin audited contracts
- Foundry's formal verification support
- Comprehensive test coverage
- Gas optimization analysis

## Gas Optimization

The contracts are optimized for Celo's low-cost environment:

- **Storage Optimization** - Efficient packing of struct data
- **Loop Optimization** - Minimized gas costs in iterations
- **Event Emission** - Efficient event structures
- **Library Usage** - Reusable components via OpenZeppelin

## Integration

### Python Integration

```python
from web3 import Web3
from contracts import IdentityRegistry, TEERegistry, ReputationRegistry

# Initialize contracts
identity = IdentityRegistry(web3, identity_address)
tee = TEERegistry(web3, tee_address)
reputation = ReputationRegistry(web3, reputation_address)

# Register agent
agent_id = identity.register("ipfs://QmMetadata", metadata)

# Add TEE key
tee.add_key(agent_id, tee_arch, measurement, pubkey, config, verifier, proof)
```

### JavaScript Integration

```javascript
import { ethers } from 'ethers';
import { IdentityRegistry, TEERegistry, ReputationRegistry } from './artifacts';

// Initialize contracts
const identity = new ethers.Contract(identityAddress, IdentityRegistry.abi, signer);
const tee = new ethers.Contract(teeAddress, TEERegistry.abi, signer);
const reputation = new ethers.Contract(reputationAddress, ReputationRegistry.abi, signer);

// Register agent
const agentId = await identity.register("ipfs://QmMetadata", metadata);
```

## Deployment Addresses

### Celo Sepolia Testnet

- IdentityRegistry: `0x...` (deployed via script)
- ReputationRegistry: `0x...` (deployed via script)
- TEERegistry: `0x...` (deployed via script)

Check `.env.deployed` for actual deployed addresses.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- 📧 Email: support@remittance-agent.example.com
- 💬 Discord: [Remittance Agent Developers](https://discord.gg/remittance)
- 📖 Documentation: [docs.remittance-agent.example.com](https://docs.remittance-agent.example.com)
