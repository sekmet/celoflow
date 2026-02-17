# CeloFlow UI

A modern, AI-powered remittance interface built on the Celo blockchain. Send money globally using natural language commands with the power of Google Gemini AI and decentralized finance.

## Overview

CeloFlow transforms how you send money internationally by turning natural language into instant blockchain transactions. Simply type "Send 50 USD to Mom in Philippines" and watch as our AI agent finds the best routes, calculates optimal exchange rates, and executes the transfer securely on the Celo blockchain.

### Key Features

- **AI-Powered Interface**: Natural language transaction processing using Google Gemini AI
- **Multi-Currency Support**: Send in cUSD, EUR, PHP, MXN, KES, BRL, JPY, and more
- **Smart Routing**: Automatic optimization through Mento Protocol and DEXs for best rates
- **TEE Security**: Trusted Execution Environment for secure key management
- **Real-Time Exchange Rates**: Live currency conversion with fallback mechanisms
- **Recurring Payments**: Set up automated transfers (daily, weekly, monthly)
- **Voice Input**: Speech-to-text support for hands-free transactions
- **Transaction History**: Complete audit trail with status tracking
- **Dark Mode**: Beautiful light/dark theme switching
- **Responsive Design**: Works seamlessly on desktop and mobile

## Technology Stack

- **Frontend**: React 19 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS with custom animations
- **Icons**: Lucide React
- **AI Integration**: Google Gemini 3 Flash Preview
- **Blockchain**: Celo Protocol with Mento stablecoins
- **Security**: Trusted Execution Environment (TEE)

## Getting Started

### Prerequisites

- Node.js 18+ 
- Bun (recommended) or npm/yarn

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd celoflow-ui
   ```

2. Install dependencies:
   ```bash
   bun install
   # or
   npm install
   ```

3. Start the development server:
   ```bash
   bun dev
   # or
   npm run dev
   ```

4. Open your browser and navigate to `http://localhost:3000`

## Usage

### Basic Transactions

Simply type natural language commands like:

- "Send 50 cUSD to Mom in Philippines"
- "Transfer 200 EUR to Juan in Mexico" 
- "Pay landlord 15000 KES via M-Pesa"

### Recurring Payments

Set up automated transfers:

- "Send 100 cUSD to Dad every month"
- "Pay 500 MXN rent weekly starting next Friday"

### Voice Input

Click the microphone button to use speech-to-text for hands-free transactions.

### Currency Conversion

The app automatically detects target currencies based on context or you can specify them directly:

- "Send 100 USD to Brazil in BRL"
- "Convert 50 cUSD to EUR for Marie in France"

## Architecture

### AI Processing Flow

1. **User Input**: Natural language message entered
2. **Gemini AI**: Parses intent, extracts amount, currency, recipient
3. **Currency Service**: Fetches real-time exchange rates
4. **Route Optimization**: Calculates best path through DEXs/Mento
5. **Transaction Preview**: Shows fees, rates, and savings
6. **User Confirmation**: One-click execution
7. **Blockchain Execution**: Secure transaction on Celo

### Security Model

- **TEE Key Management**: Private keys never leave secure enclave
- **Gas Abstraction**: Pay fees in sent currency, no CELO needed
- **Multi-Sig Support**: Additional security layers for large amounts
- **Audit Trail**: Complete transaction history with status tracking

## Development

### Scripts

| Command | Description |
|---------|-------------|
| `bun dev` | Start development server |
| `bun build` | Build for production |
| `bun preview` | Preview production build |

### Code Style

- TypeScript strict mode enabled
- Functional components with hooks
- Tailwind CSS for styling
- Lucide React for icons
- No `any` types allowed

### Testing

```bash
bun test  # Run tests
```

## API Integration

- Support multiple languages (English, Spanish, Portuguese, French)
- Parse transaction intent with high accuracy
- Handle ambiguous requests gracefully
- Provide contextual responses

### Exchange Rates

- In Progress

## Deployment

### Build for Production

```bash
bun build
```

## License

This project is licensed under the MIT License.

## Support

For support and questions:

- Create an issue in the repository
- Check the documentation
- Review existing issues for common problems
