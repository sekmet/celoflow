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
  error: '❌',
  idle: '',
} as const;

const STATUS_MESSAGES = {
  thinking: 'Thinking...',
  routing: 'Routing...',
  checking: 'Checking...',
  finding: 'Finding...',
  loading: 'Loading...',
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
 * Animated status indicator showing LLM operation progress
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
  
  // Combine base message with operation context
  const fullMessage = operationMessage 
    ? `${baseMessage} ${operationMessage}...`
    : baseMessage;
  
  return (
    <div className={`flex items-center gap-2 text-sm text-gray-500 dark:text-gray-200 font-medium animate-fade-in-up px-3 py-2 ${className}`}>
      <span className={`text-lg ${displayStatus === 'error' ? 'animate-bounce' : 'animate-pulse'}`}>
        {icon}
      </span>
      <span>{fullMessage}</span>
    </div>
  );
};
