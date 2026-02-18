import React from 'react';
import { LLMStatus, LLMStatusState } from '../types/llm-status';
import { useI18n } from '../lib/language';

interface LLMStatusIndicatorProps {
  status: LLMStatusState;
  className?: string;
}

const STATUS_ICONS = {
  thinking: '🤖',
  routing: '🔄', 
  checking: '✅',
  finding: '🔍',
  loading: '⚡',
  swapping: '💱',
  transferring: '💸',
  checking_balance: '💰',
  compliance_check: '🛡️',
  tee_verification: '🔐',
  kyc_check: '🆔',
  route_finding: '🗺️',
  error: '❌',
  idle: '',
} as const;

const STATUS_MESSAGES = {
  thinking: 'Thinking...',
  routing: 'Routing...',
  checking: 'Checking...',
  finding: 'Finding...',
  loading: 'Loading...',
  swapping: 'Swapping...',
  transferring: 'Transferring...',
  checking_balance: 'Checking balance...',
  compliance_check: 'Compliance check...',
  tee_verification: 'TEE verification...',
  kyc_check: 'KYC check...',
  route_finding: 'Finding route...',
  error: 'Error occurred',
  idle: '',
} as const;

const OPERATION_MESSAGES = {
  transfer: 'transfer',
  swap: 'swap',
  balance: 'balance',
  contact: 'contact',
  rate: 'rates',
} as const;

/**
 * Animated status indicator showing LLM operation progress with real-time details
 */
export const LLMStatusIndicator: React.FC<LLMStatusIndicatorProps> = ({ 
  status, 
  className = '' 
}) => {
  const { t } = useI18n();
  
  // Always show something during streaming, even if status is idle
  const displayStatus = status.status === 'idle' ? 'thinking' : status.status;
  
  const icon = STATUS_ICONS[displayStatus];
  const baseMessage = t(STATUS_MESSAGES[displayStatus]);
  const operationMessage = status.operation ? t(OPERATION_MESSAGES[status.operation as keyof typeof OPERATION_MESSAGES]) : '';
  
  // Build detailed message with real-time operation details
  const buildDetailedMessage = () => {
    // If we have a real-time message, use it
    if (status.message && status.realTimeEnabled) {
      return status.message;
    }
    
    // Combine base message with operation context
    let message = operationMessage 
      ? `${baseMessage} ${operationMessage}...`
      : baseMessage;
    
    // Add specific operation details
    if (status.amount && status.token) {
      if (displayStatus === 'swapping') {
        message += ` ${status.amount} ${status.token}`;
      } else if (displayStatus === 'transferring') {
        message += ` ${status.amount} ${status.token}`;
        if (status.recipient) {
          message += ` to ${status.recipient.slice(0, 6)}...${status.recipient.slice(-4)}`;
        }
      }
    }
    
    return message;
  };
  
  const fullMessage = buildDetailedMessage();
  
  // Show connection status indicator
  const ConnectionIndicator = () => {
    if (status.realTimeEnabled === undefined) return null;
    
    return (
      <span 
        className={`text-xs ${
          status.connected 
            ? 'text-green-500' 
            : status.realTimeEnabled 
              ? 'text-yellow-500' 
              : 'text-gray-400'
        }`}
        title={
          status.connected 
            ? 'Real-time status connected' 
            : status.realTimeEnabled 
              ? 'Real-time status disconnected' 
              : 'Using timing-based heuristics'
        }
      >
        {status.connected ? '●' : status.realTimeEnabled ? '○' : '◐'}
      </span>
    );
  };
  
  // Show progress bar for operations with progress
  const ProgressBar = () => {
    if (status.progress === undefined || status.progress <= 0) return null;
    
    return (
      <div className="w-16 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div 
          className="h-full bg-blue-500 transition-all duration-300 ease-out"
          style={{ width: `${status.progress * 100}%` }}
        />
      </div>
    );
  };
  
  // Show transaction link if available
  const TransactionLink = () => {
    if (!status.transactionHash) return null;
    
    const explorerUrl = `https://celoscan.io/tx/${status.transactionHash}`;
    
    return (
      <a 
        href={explorerUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-500 hover:text-blue-700 text-xs underline ml-2"
        title="View transaction on CeloScan"
      >
        View Tx
      </a>
    );
  };
  
  // Show error message if present
  const ErrorMessage = () => {
    if (!status.error && displayStatus !== 'error') return null;
    
    const errorMessage = status.error || 'An error occurred during processing';
    
    return (
      <div className="text-red-500 text-xs mt-1 max-w-xs">
        {errorMessage}
      </div>
    );
  };
  
  return (
    <div className={`flex flex-col gap-1 text-sm text-gray-500 dark:text-gray-200 font-medium animate-fade-in-up px-3 py-2 ${className}`}>
      <div className="flex items-center gap-2">
        <ConnectionIndicator />
        <span className={`text-lg ${displayStatus === 'error' ? 'animate-bounce' : 'animate-pulse'}`}>
          {icon}
        </span>
        <span className="flex-1">{fullMessage}</span>
        <ProgressBar />
        <TransactionLink />
      </div>
      <ErrorMessage />
    </div>
  );
};
