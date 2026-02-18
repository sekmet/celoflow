import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Send, Bot, CheckCircle2, ChevronRight, Loader2, RefreshCcw, History, CalendarClock, X, Search, Zap, TrendingUp, AlertCircle, Mic, ChevronDown, Info, Ban, Share2, Wallet } from 'lucide-react';
import { useAccount } from 'wagmi';
import { MarkdownContent } from './MarkdownContent';
import { LLMStatusIndicator } from './LLMStatusIndicator';
import { WalletAuthorizationModal } from './WalletAuthorizationModal';
import { QuickTransferModal, type TransferCompletedResult } from './QuickTransferModal';
import { TransferPreviewModal } from './TransferPreviewModal';
import { useUserSigning } from '../hooks/useUserSigning';
import { streamChat, type ChatMessage as CeloflowMessage, type WalletContext, type ContactData, type LLMStatusState } from '../lib/celoflow-client';
import { getContacts } from '../services/contactsService';
import { getExchangeRate } from '../services/currencyService';
import { addTransaction, updateTransactionStatus, getTransactionHistory, cancelTransaction } from '../services/transactionHistoryService';
import { getUserSettings, UserSettings } from '../services/userSettingsService';
import { Message, TransactionIntent, TransactionHistoryItem, TransferPreview } from '../types';
import { SUGGESTED_PROMPTS, SUPPORTED_CURRENCIES } from '../constants';
import { useI18n } from '../lib/language';

interface ChatInterfaceProps {
  className?: string;
  fullScreen?: boolean;
}

interface SpeechRecognitionResultItem {
  transcript: string;
}

interface SpeechRecognitionResultEventLike {
  results: ArrayLike<ArrayLike<SpeechRecognitionResultItem>>;
}

interface SpeechRecognitionErrorEventLike {
  error?: string;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onresult: ((event: SpeechRecognitionResultEventLike) => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null;

  const speechWindow = window as Window & {
    SpeechRecognition?: unknown;
    webkitSpeechRecognition?: unknown;
  };

  const ctor = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
  if (typeof ctor !== 'function') return null;

  return ctor as SpeechRecognitionConstructor;
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException) return error.name === 'AbortError';

  if (typeof error === 'object' && error !== null && 'name' in error) {
    const namedError = error as { name?: string };
    return namedError.name === 'AbortError';
  }

  return false;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '', fullScreen = false }) => {
  const { address, isConnected, chain } = useAccount();
  const { t, language } = useI18n();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: t('Hi! I\'m CeloFlow. I can help you send money globally using the Celo blockchain. Where would you like to send money today?'),
      type: 'text'
    }
  ]);

  // Update initial message when language changes
  const welcomeMessageKey = 'Hi! I\'m CeloFlow. I can help you send money globally using the Celo blockchain. Where would you like to send money today?';
  
  useEffect(() => {
    setMessages(prev => {
      const updated = [...prev];
      if (updated.length > 0 && updated[0].id === '1') {
        const newContent = t(welcomeMessageKey);
        if (updated[0].content !== newContent) {
          updated[0] = {
            ...updated[0],
            content: newContent
          };
        }
      }
      return updated;
    });
  }, [language]); // Depend on language, not t function
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<LLMStatusState>({ status: 'idle', timestamp: Date.now() });
  const abortRef = useRef<AbortController | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<TransactionHistoryItem[]>(() => getTransactionHistory());
  const [historySearch, setHistorySearch] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [userCurrency, setUserCurrency] = useState('USD');
  const [localEstimates, setLocalEstimates] = useState<Record<string, { source: string, target: string }>>({});
  const [expandedFees, setExpandedFees] = useState<string | null>(null);
  const [showWalletAuth, setShowWalletAuth] = useState(false);
  const [pendingConfirmMsgId, setPendingConfirmMsgId] = useState<string | null>(null);
  const [showQuickTransfer, setShowQuickTransfer] = useState(false);
  const [userWalletTxHash, setUserWalletTxHash] = useState<string | null>(null);
  const [showTransferPreview, setShowTransferPreview] = useState(false);
  const [transferPreviewData, setTransferPreviewData] = useState<TransferPreview | null>(null);
  const [isExecutingPreview, setIsExecutingPreview] = useState(false);

  // User wallet signing hook
  const userSigning = useUserSigning();

  // User settings for fee comparison preference
  const [userSettings, setUserSettings] = useState<UserSettings | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const isUserScrolling = useRef(false);

  // Create wallet context for the agent (memoized to prevent infinite re-renders)
  const walletContext = useMemo((): WalletContext => {
    if (isConnected && address) {
      return {
        wallet_address: address,
        connected: true,
        chain_id: chain?.id,
        balances: {} // Will be populated by backend
      };
    } else {
      return {
        connected: false,
        balances: {}
      };
    }
  }, [address, isConnected, chain?.id]);

  // Debounced wallet context update to prevent spamming backend
  const updateWalletContextBackend = useCallback(async (context: WalletContext) => {
    try {
      await fetch('http://localhost:8000/wallet/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: context.wallet_address,
          connected: context.connected,
          chainId: context.chain_id
        })
      });
    } catch (err) {
      console.warn('Failed to update wallet context:', err);
    }
  }, []);

  // Update wallet context in backend when it changes (with debouncing)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (walletContext) {
        updateWalletContextBackend(walletContext);
      }
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [walletContext, updateWalletContextBackend]);

  useEffect(() => {
    if (scrollRef.current) {
      const scrollContainer = scrollRef.current;
      
      // Only auto-scroll if user is not manually scrolling or is already at bottom
      const isAtBottom = scrollContainer.scrollHeight - scrollContainer.scrollTop <= scrollContainer.clientHeight + 50; // 50px tolerance
      
      if (!isUserScrolling.current || isAtBottom) {
        // Smooth scroll to bottom when messages change or fees expand
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: 'smooth'
        });
      }
      
      // Reset user scrolling flag after a short delay
      const timeoutId = setTimeout(() => {
        isUserScrolling.current = false;
      }, 1000);
      
      return () => clearTimeout(timeoutId);
    }
  }, [messages, expandedFees, isStreaming]); // Also trigger on streaming state changes

  // Additional effect to handle streaming content updates
  useEffect(() => {
    if (isStreaming && scrollRef.current) {
      const scrollContainer = scrollRef.current;
      const isAtBottom = scrollContainer.scrollHeight - scrollContainer.scrollTop <= scrollContainer.clientHeight + 50;
      
      if (!isUserScrolling.current || isAtBottom) {
        // Force scroll during streaming
        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: 'smooth'
        });
      }
    }
  }, [isStreaming, streamingMsgId]); // Trigger when streaming starts or message ID changes

  // Handle scroll events to detect user scrolling
  const handleScroll = useCallback(() => {
    if (scrollRef.current) {
      const scrollContainer = scrollRef.current;
      const isAtBottom = scrollContainer.scrollHeight - scrollContainer.scrollTop <= scrollContainer.clientHeight + 50;
      
      // Mark as user scrolling if not at bottom
      if (!isAtBottom) {
        isUserScrolling.current = true;
      } else {
        isUserScrolling.current = false;
      }
    }
  }, []);

  // Detect user local currency on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && window.Intl) {
        try {
            const currency = new Intl.NumberFormat().resolvedOptions().currency;
            if (currency) setUserCurrency(currency);
        } catch (e) {
            console.warn('Could not detect local currency', e);
        }
    }
  }, []);

  // Load user settings on mount
  useEffect(() => {
    const loadUserSettings = async () => {
      try {
        const settings = await getUserSettings('default');
        setUserSettings(settings);
      } catch (error) {
        console.warn('Failed to load user settings:', error);
        // Use default settings as fallback
        setUserSettings({
          userId: 'default',
          showFeeComparison: true,
          defaultCurrency: 'USDm',
          language: 'en',
          theme: 'auto',
          notifications: {
            transfers: true,
            recurring: true,
            failures: true,
          },
          privacy: {
            shareAnalytics: false,
            saveHistory: true,
          },
        });
      }
    };
    loadUserSettings();
  }, []);

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = getSpeechRecognitionConstructor();
    if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = 'en-US';

            recognitionRef.current.onstart = () => setIsListening(true);
            recognitionRef.current.onend = () => setIsListening(false);
            recognitionRef.current.onerror = (event: SpeechRecognitionErrorEventLike) => {
                console.error('Speech recognition error', event.error);
                setIsListening(false);
            };
            
            recognitionRef.current.onresult = (event: SpeechRecognitionResultEventLike) => {
                const transcript = event.results[0]?.[0]?.transcript || '';
                if (!transcript) return;
                setInput(prev => {
                    const spacer = prev.length > 0 && !prev.endsWith(' ') ? ' ' : '';
                    return prev + spacer + transcript;
                });
            };
    }
  }, []);

  // Calculate local estimates when a new preview message arrives
  useEffect(() => {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg?.type === 'transaction_preview' && lastMsg.transactionData && !localEstimates[lastMsg.id]) {
          const calculateEstimates = async () => {
              const data = lastMsg.transactionData!;
              // Avoid redundant calls if currencies match
              let sourceEst = '';
              let targetEst = '';

              if (data.currency !== userCurrency) {
                  const { rate } = await getExchangeRate(data.currency, userCurrency);
                  sourceEst = `≈ ${(data.amount * rate).toFixed(2)} ${userCurrency}`;
              }

              if (data.recipientCurrency !== userCurrency) {
                   const { rate } = await getExchangeRate(data.recipientCurrency, userCurrency);
                   targetEst = `≈ ${(data.convertedAmount * rate).toFixed(2)} ${userCurrency}`;
              }

              if (sourceEst || targetEst) {
                  setLocalEstimates(prev => ({
                      ...prev,
                      [lastMsg.id]: { source: sourceEst, target: targetEst }
                  }));
              }
          };
          calculateEstimates();
      }
  }, [messages, userCurrency]);


  const toggleListening = () => {
    if (!recognitionRef.current) {
        alert(t('Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.'));
        return;
    }
    if (isListening) {
        recognitionRef.current.stop();
    } else {
        recognitionRef.current.start();
    }
  };

  const handleSend = async (text: string = input) => {
    if (!text.trim() || isStreaming) return;

    // Abort any previous stream
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // Add User Message
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // Prepare an empty assistant message for streaming
    const assistantId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      type: 'text',
    };
    setMessages(prev => [...prev, assistantMsg]);
    setStreamingMsgId(assistantId);
    setIsStreaming(true);
    console.log('Starting streaming, isStreaming set to true');
    setIsLoading(false);

    // Build messages array for the backend
    const chatMessages: CeloflowMessage[] = messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role as 'user' | 'assistant', content: m.content }))
      .concat({ role: 'user', content: text });

    // Use requestAnimationFrame batching for smooth rendering
    let pendingContent = '';
    let rafId: number | null = null;

    const flushContent = () => {
      const content = pendingContent;
      setMessages(prev =>
        prev.map(m => (m.id === assistantId ? { ...m, content } : m)),
      );
      
      // Trigger scroll after content update
      if (scrollRef.current && (!isUserScrolling.current || 
          (scrollRef.current.scrollHeight - scrollRef.current.scrollTop <= scrollRef.current.clientHeight + 50))) {
        setTimeout(() => {
          scrollRef.current?.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: 'smooth'
          });
        }, 10); // Small delay to ensure DOM is updated
      }
      
      rafId = null;
    };

    // Load contacts to send with the request
    let contactsData: ContactData[] = [];
    try {
      const allContacts = await getContacts();
      contactsData = allContacts
        .filter(c => !c.blocked)
        .map(c => ({
          id: c.id,
          name: c.name,
          address: c.address,
          network: c.network,
          city: c.city,
          country: c.country,
          phone: c.phone,
          email: c.email,
          notes: c.notes,
          favorite: c.favorite,
          blocked: c.blocked,
          group: c.group,
        }));
    } catch (err) {
      console.warn('Failed to load contacts for chat:', err);
    }

    try {
      await streamChat({
        messages: chatMessages,
        walletContext,
        contacts: contactsData,
        userSettings,
        signal: controller.signal,
        onContent: (fullContent) => {
          pendingContent = fullContent;
          if (!rafId) {
            rafId = requestAnimationFrame(flushContent);
          }
        },
        onComplete: (fullContent) => {
          // Ensure final content is flushed
          if (rafId) cancelAnimationFrame(rafId);
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, content: fullContent } : m,
            ),
          );
        },
        onStatus: (statusState) => {
          console.log('LLM Status Update:', statusState);
          setLlmStatus(statusState);
        },
      });
    } catch (error: unknown) {
      if (!isAbortError(error)) {
        console.error('Stream error:', error);
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? {
                  ...m,
                  content:
                    m.content ||
                    t('Sorry, I encountered an error connecting to the server. Please try again.'),
                }
              : m,
          ),
        );
      }
    } finally {
      if (rafId) cancelAnimationFrame(rafId);
      setIsStreaming(false);
      setStreamingMsgId(null);
      setLlmStatus({ status: 'idle', timestamp: Date.now() });
    }
  };

  const updateTransactionData = (msgId: string, updates: Partial<TransactionIntent>) => {
    setMessages(prev => prev.map(msg => {
        if (msg.id === msgId && msg.transactionData) {
            return {
                ...msg,
                transactionData: { ...msg.transactionData, ...updates }
            };
        }
        return msg;
    }));
  };

  const handleCurrencyChange = async (msgId: string, type: 'source' | 'target', newCurrency: string) => {
      const msgIndex = messages.findIndex(m => m.id === msgId);
      if (msgIndex === -1) return;
      
      const msg = messages[msgIndex];
      if (!msg.transactionData) return;

      const currentData = msg.transactionData;
      const source = type === 'source' ? newCurrency : currentData.currency;
      const target = type === 'target' ? newCurrency : currentData.recipientCurrency;

      // Optimistic update for UI selection
      updateTransactionData(msgId, {
          currency: source,
          recipientCurrency: target,
          exchangeRate: 0 // Show as calculating
      });

      try {
          const { rate, isRealTime } = await getExchangeRate(source, target);
          const converted = currentData.amount * rate;
          
          updateTransactionData(msgId, {
              currency: source,
              recipientCurrency: target,
              exchangeRate: parseFloat(rate.toFixed(4)),
              convertedAmount: parseFloat(converted.toFixed(2)),
              isRealTimeRate: isRealTime
          });

          // Refresh local estimates
          const rateToLocalSource = await getExchangeRate(source, userCurrency);
          const rateToLocalTarget = await getExchangeRate(target, userCurrency);
          
          setLocalEstimates(prev => ({
            ...prev,
            [msgId]: { 
                source: source !== userCurrency ? `≈ ${(currentData.amount * rateToLocalSource.rate).toFixed(2)} ${userCurrency}` : '',
                target: target !== userCurrency ? `≈ ${(converted * rateToLocalTarget.rate).toFixed(2)} ${userCurrency}` : ''
            }
          }));

      } catch (error) {
          console.error("Failed to update rate", error);
      }
  };

  const handleConfirm = (transactionId: string) => {
    // If wallet is connected, show authorization choice modal
    if (isConnected && address) {
      setPendingConfirmMsgId(transactionId);
      const msg = messages.find(m => m.id === transactionId);
      if (msg?.transactionData) {
        // Resolve recipient name → wallet address via contacts
        const recipientRaw = msg.transactionData.recipient || '';
        const isAddress = /^0x[0-9a-fA-F]{40}$/.test(recipientRaw.trim());
        const resolveAndPrepare = async () => {
          let recipientAddress = recipientRaw.trim();
          if (!isAddress) {
            try {
              const allContacts = await getContacts();
              const match = allContacts.find(
                c => c.name.toLowerCase() === recipientRaw.toLowerCase().trim()
              );
              if (match) recipientAddress = match.address;
            } catch {
              // non-critical — fall through with raw value
            }
          }
          await userSigning.prepare(
            recipientAddress,
            msg.transactionData!.amount || 0,
            msg.transactionData!.recipientCurrency || msg.transactionData!.currency || 'USDm',
          );
          setShowWalletAuth(true);
        };
        resolveAndPrepare();
      }
      return;
    }

    // No wallet connected — use TEE agent wallet (original flow)
    executeConfirmWithTEE(transactionId);
  };

  const executeConfirmWithTEE = (transactionId: string) => {
    setMessages(prev => {
        const updated = prev.map(msg => {
            if (msg.id === transactionId && msg.type === 'transaction_preview' && msg.transactionData) {
                
                const isRecurring = msg.transactionData.frequency && msg.transactionData.frequency !== 'one-time';
                const initialStatus: TransactionHistoryItem['status'] = isRecurring ? 'scheduled' : 'processing';

                const historyItem = addTransaction(msg.transactionData, initialStatus);
                setHistory(h => [historyItem, ...h.filter(i => i.id !== historyItem.id)]);
                
                if (!isRecurring) {
                    setTimeout(() => {
                        updateTransactionStatus(historyItem.id, 'completed');
                        setHistory(currentHistory => currentHistory.map(item => 
                            item.id === historyItem.id && item.status !== 'cancelled'
                                ? { ...item, status: 'completed' } 
                                : item
                        ));
                    }, 4000);
                }
                
                return { ...msg, type: 'transaction_success' as const };
            }
            return msg;
        });
        return updated;
    });
  };

  const handleChooseTEE = () => {
    setShowWalletAuth(false);
    if (pendingConfirmMsgId) {
      executeConfirmWithTEE(pendingConfirmMsgId);
      setPendingConfirmMsgId(null);
    }
    userSigning.reset();
  };

  const handleChooseUserWallet = async () => {
    const result = await userSigning.signAndExecute();
    if (result && result.status === 'success' && pendingConfirmMsgId) {
      const txHash = result.tx_hash ?? '';
      const explorerUrl = result.explorer_url ?? `https://sepolia.celoscan.io/tx/${txHash}`;
      setUserWalletTxHash(txHash);
      setMessages(prev => prev.map(msg => {
        if (msg.id === pendingConfirmMsgId && msg.type === 'transaction_preview' && msg.transactionData) {
          const historyItem = addTransaction(msg.transactionData, 'completed');
          setHistory(h => [historyItem, ...h.filter(i => i.id !== historyItem.id)]);
          return {
            ...msg,
            type: 'transaction_success' as const,
            // Attach tx hash + signer info for the success card
            transactionData: {
              ...msg.transactionData,
              txHash,
              explorerUrl,
              signerType: 'user' as const,
            },
          };
        }
        return msg;
      }));
      setPendingConfirmMsgId(null);
      // Close the modal after a short delay so user sees the confirmed state
      setTimeout(() => setShowWalletAuth(false), 1800);
    }
  };

  const handleRetryWithTEE = () => {
    setShowWalletAuth(false);
    if (pendingConfirmMsgId) {
      executeConfirmWithTEE(pendingConfirmMsgId);
      setPendingConfirmMsgId(null);
    }
    userSigning.reset();
  };

  const handleCloseWalletAuth = () => {
    setShowWalletAuth(false);
    setPendingConfirmMsgId(null);
    userSigning.reset();
  };

  const handleShowTransferPreview = useCallback(async (
    recipientAddress: string,
    amount: number,
    token: string,
    destinationCountry: string = '',
  ) => {
    try {
      const response = await fetch('http://localhost:8000/transfer/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_address: recipientAddress,
          amount,
          token,
          destination_country: destinationCountry,
          from_currency: 'USD',
          user_id: address ?? 'unknown',
        }),
      });
      if (!response.ok) {
        console.warn('Transfer preview failed:', response.status);
        return null;
      }
      const preview = await response.json() as TransferPreview;
      if (preview.error) {
        console.warn('Transfer preview error:', preview.error);
        return null;
      }
      setTransferPreviewData(preview);
      setShowTransferPreview(true);
      return preview;
    } catch (err) {
      console.warn('Failed to fetch transfer preview:', err);
      return null;
    }
  }, [address]);

  const handlePreviewConfirm = useCallback(async (previewId: string) => {
    setIsExecutingPreview(true);
    try {
      const response = await fetch('http://localhost:8000/api/transfers/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient: transferPreviewData?.recipient,
          amount: transferPreviewData?.amount,
          currency: transferPreviewData?.token,
          preview_id: previewId,
          user_id: address ?? 'unknown',
        }),
      });
      const result = await response.json() as { success: boolean; result?: string; error?: string };
      if (result.success) {
        const successMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `✅ Transfer complete! **${transferPreviewData?.amount} ${transferPreviewData?.token}** sent via TEE agent wallet. ${result.result ?? ''}`,
          type: 'text',
        };
        setMessages(prev => [...prev, successMsg]);
      } else {
        const errMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: `❌ Transfer failed: ${result.error ?? 'Unknown error'}`,
          type: 'text',
        };
        setMessages(prev => [...prev, errMsg]);
      }
    } catch (err) {
      console.error('Preview execution error:', err);
    } finally {
      setIsExecutingPreview(false);
      setShowTransferPreview(false);
      setTransferPreviewData(null);
    }
  }, [transferPreviewData, address]);

  const handlePreviewCancel = useCallback(() => {
    setShowTransferPreview(false);
    setTransferPreviewData(null);
    setIsExecutingPreview(false);
  }, []);

  const handleQuickTransferComplete = useCallback((result: TransferCompletedResult) => {
    const successMsg = {
      id: Date.now().toString(),
      role: 'assistant' as const,
      content: `✅ Transfer sent! **${result.amount} ${result.token}** to **${result.recipient}**. [View on CeloScan](${result.explorerUrl})`,
      type: 'text' as const,
    };
    setMessages(prev => [...prev, successMsg]);
    setShowQuickTransfer(false);
  }, []);

  const handleCancelTransaction = (historyId: string) => {
      if (window.confirm(t('Are you sure you want to cancel this scheduled payment?'))) {
          cancelTransaction(historyId);
          setHistory(prev => prev.map(item => 
              item.id === historyId ? { ...item, status: 'cancelled' } : item
          ));
      }
  };

  const handleShare = async (msg: Message) => {
      const data = msg.transactionData;
      if (!data) return;

      const shareData = {
          title: t('CeloFlow Transaction'),
          text: t('I just sent {{amount}} {{currency}} to {{recipient}} via CeloFlow!', {
            amount: data.amount,
            currency: data.currency,
            recipient: data.recipient,
          }),
          url: window.location.href
      };

      try {
          if (navigator.share) {
              await navigator.share(shareData);
          } else {
              await navigator.clipboard.writeText(shareData.text);
              alert(t('Transaction details copied to clipboard!'));
          }
      } catch (err) {
          console.error("Error sharing:", err);
      }
  };

  const filteredHistory = history.filter(item => 
    item.intent.recipient.toLowerCase().includes(historySearch.toLowerCase()) ||
    item.intent.recipientCurrency.toLowerCase().includes(historySearch.toLowerCase()) ||
    item.intent.currency.toLowerCase().includes(historySearch.toLowerCase())
  );

  const getStatusConfig = (status: TransactionHistoryItem['status']) => {
      switch(status) {
          case 'completed': return {
              class: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
              tooltip: t('Funds have successfully reached the recipient.')
          };
          case 'processing': return {
              class: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
              tooltip: t('Transaction is currently being confirmed on the blockchain.')
          };
          case 'scheduled': return {
              class: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
              tooltip: t('Payment is set to execute at a future date.')
          };
          case 'cancelled': return {
              class: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400',
              tooltip: t('This transaction was cancelled by the user.')
          };
          case 'failed': return {
              class: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
              tooltip: t('Transaction could not be completed. Please try again.')
          };
          default: return { class: 'bg-gray-100 text-gray-700', tooltip: '' };
      }
  };

  const containerClasses = fullScreen 
    ? `w-full h-full flex flex-col bg-white dark:bg-gray-800 overflow-hidden relative transition-colors duration-300 ${className}`
    : `w-full max-w-md mx-auto h-[85vh] md:h-[600px] flex flex-col bg-white dark:bg-gray-800 md:rounded-[2rem] rounded-xl shadow-2xl border border-gray-100 dark:border-gray-700 overflow-hidden relative transition-colors duration-300 ${className}`;

  return (
    <div className={containerClasses}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between bg-white dark:bg-gray-800 z-10 shrink-0">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-celo-green/10 flex items-center justify-center">
                    <Bot className="w-6 h-6 text-celo-green" />
                </div>
                <div>
                    <h3 className="font-bold text-gray-900 dark:text-white">CeloFlow</h3>
                    <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">{t('Online')}</span>
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-1">
                <button 
                    onClick={() => setShowHistory(!showHistory)}
                    className={`p-2 rounded-full transition-colors ${showHistory ? 'bg-celo-green text-white' : 'hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-400'}`}
                    title={t('Transaction History')}
                >
                    <History className="w-4 h-4" />
                </button>
                <button className="p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-full transition-colors">
                    <RefreshCcw className="w-4 h-4 text-gray-400" onClick={() => setMessages([messages[0]])}/>
                </button>
            </div>
        </div>

        {/* History Overlay */}
        {showHistory && (
            <div className="absolute inset-0 top-[73px] bg-white dark:bg-gray-800 z-20 overflow-y-auto p-4 animate-fade-in-up">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-lg text-gray-900 dark:text-white">{t('Recent Activity')}</h3>
                    <button onClick={() => setShowHistory(false)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full">
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                <div className="mb-4 relative">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                    <input
                        type="text"
                        placeholder={t('Search recipient or currency...')}
                        value={historySearch}
                        onChange={(e) => setHistorySearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green placeholder-gray-500 dark:placeholder-gray-400"
                    />
                </div>

                {filteredHistory.length === 0 ? (
                    <div className="text-center text-gray-400 mt-10">
                        {history.length === 0 ? t('No transactions yet.') : t('No matching transactions.')}
                    </div>
                ) : (
                    <div className="space-y-3">
                        {filteredHistory.map(item => {
                            const statusConfig = getStatusConfig(item.status);
                            return (
                                <div key={item.id} className="p-4 rounded-xl border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
                                    <div className="flex justify-between items-start mb-2">
                                        <div>
                                            <p className="font-bold text-gray-900 dark:text-white">
                                                {item.intent.recipient}
                                            </p>
                                            <p className="text-xs text-gray-500">{item.date}</p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {item.status === 'scheduled' && (
                                                <button 
                                                    onClick={() => handleCancelTransaction(item.id)}
                                                    className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-full transition-colors"
                                                    title={t('Cancel Scheduled Payment')}
                                                >
                                                    <Ban className="w-4 h-4" />
                                                </button>
                                            )}
                                            <div className="relative group">
                                                <div className={`px-2 py-1 rounded text-[10px] font-bold uppercase flex items-center gap-1 cursor-help ${statusConfig.class}`}>
                                                    {item.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                                                    {t(item.status)}
                                                </div>
                                                {/* Tooltip */}
                                                <div className="absolute bottom-full right-0 mb-2 hidden group-hover:block w-48 bg-gray-900 text-white text-xs p-2 rounded shadow-lg z-50">
                                                    {statusConfig.tooltip}
                                                    <div className="absolute -bottom-1 right-3 w-2 h-2 bg-gray-900 rotate-45"></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div className="flex flex-col gap-1 mt-3 pt-3 border-t border-gray-100 dark:border-gray-600/50">
                                        <div className="flex justify-between text-sm">
                                            <span className="text-gray-500 text-xs uppercase tracking-wider">{t('Sent')}</span>
                                            <span className="font-medium text-gray-900 dark:text-white">{item.intent.amount} {item.intent.currency}</span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="text-gray-500 text-xs uppercase tracking-wider">{t('Received')}</span>
                                            <span className="font-bold text-celo-green">{item.intent.convertedAmount} {item.intent.recipientCurrency}</span>
                                        </div>
                                    </div>

                                    {item.intent.frequency && item.intent.frequency !== 'one-time' && (
                                         <div className="mt-3 text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1 bg-blue-50 dark:bg-blue-900/20 p-2 rounded-lg">
                                             <CalendarClock className="w-3 h-3" />
                                             {t('{{frequency}} starting {{startDate}}', {
                                               frequency: item.intent.frequency,
                                               startDate: item.intent.startDate || '',
                                             })}
                                         </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        )}

        {/* Chat Area */}
        <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4 space-y-6 bg-gray-50/50 dark:bg-gray-900/50 scroll-smooth">
            {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`}>
                    <div className={`max-w-[90%] ${msg.role === 'user' ? 'order-1' : 'order-2'}`}>
                        {/* Avatar */}
                        {msg.role === 'assistant' && msg.type === 'text' && (
                             <div className="text-sm bg-white dark:bg-gray-700 dark:text-gray-100 p-4 rounded-2xl rounded-tl-none shadow-sm text-gray-700 border border-gray-100 dark:border-gray-600">
                                <MarkdownContent content={msg.content} />
                             </div>
                        )}

                        {msg.role === 'user' && (
                             <div className="text-sm bg-gray-900 dark:bg-celo-green text-white p-4 rounded-2xl rounded-tr-none shadow-md">
                                <MarkdownContent content={msg.content} />
                             </div>
                        )}

                        {/* Transaction Card */}
                        {msg.role === 'assistant' && msg.type === 'transaction_preview' && msg.transactionData && (
                            <div className="bg-white dark:bg-gray-700 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-600 overflow-hidden transform transition-all">
                                <div className="p-4 border-b border-gray-50 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-800/30">
                                    <div className="text-sm text-gray-600 dark:text-gray-300 mb-1"><MarkdownContent content={msg.content} /></div>
                                    <div className="flex items-center justify-between mt-3">
                                        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('Best Quote Found')}</span>
                                        <div className="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">
                                            <CheckCircle2 className="w-3 h-3" />
                                            {t('Saved ${{amount}}', { amount: msg.transactionData.savings.toFixed(2) })}
                                        </div>
                                    </div>
                                </div>
                                <div className="p-5 space-y-4">
                                    <div className="flex justify-between items-center">
                                        <div className="flex-1">
                                            <p className="text-xs text-gray-400 mb-1">{t('You Send')}</p>
                                            <div className="flex flex-col">
                                                <div className="flex items-baseline gap-2">
                                                    <span className="text-xl font-bold text-gray-900 dark:text-white">{msg.transactionData.amount}</span>
                                                    <div className="relative">
                                                        <select
                                                            value={msg.transactionData.currency}
                                                            onChange={(e) => handleCurrencyChange(msg.id, 'source', e.target.value)}
                                                            className="appearance-none bg-transparent font-bold text-gray-500 dark:text-gray-400 text-sm pr-4 outline-none cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                                                        >
                                                            {SUPPORTED_CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                                                        </select>
                                                        <ChevronDown className="w-3 h-3 absolute right-0 top-1.5 text-gray-400 pointer-events-none" />
                                                    </div>
                                                </div>
                                                {localEstimates[msg.id]?.source && (
                                                    <span className="text-[10px] text-gray-400">{localEstimates[msg.id].source}</span>
                                                )}
                                            </div>
                                        </div>
                                        
                                        <div className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-600 flex items-center justify-center shrink-0 mx-2">
                                            <ChevronRight className="w-4 h-4 text-gray-400 dark:text-gray-300 rotate-90 md:rotate-0" />
                                        </div>
                                        
                                        <div className="text-right flex-1">
                                            <p className="text-xs text-gray-400 mb-1">{msg.transactionData.recipient} {t('Receives')}</p>
                                            <div className="flex flex-col items-end">
                                                <div className="flex items-baseline gap-2 justify-end">
                                                    <span className="text-xl font-bold text-celo-green">
                                                        {msg.transactionData.exchangeRate === 0 ? '...' : msg.transactionData.convertedAmount}
                                                    </span>
                                                    <div className="relative">
                                                        <select
                                                            value={msg.transactionData.recipientCurrency}
                                                            onChange={(e) => handleCurrencyChange(msg.id, 'target', e.target.value)}
                                                            className="appearance-none bg-transparent font-bold text-gray-500 dark:text-gray-400 text-sm pr-4 outline-none cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 transition-colors dir-rtl"
                                                        >
                                                            {SUPPORTED_CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
                                                        </select>
                                                        <ChevronDown className="w-3 h-3 absolute right-0 top-1.5 text-gray-400 pointer-events-none" />
                                                    </div>
                                                </div>
                                                {localEstimates[msg.id]?.target && (
                                                    <span className="text-[10px] text-gray-400">{localEstimates[msg.id].target}</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Prominent Exchange Rate Display with Indicator */}
                                    <div className="flex items-center justify-center py-2 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 gap-2">
                                        {msg.transactionData.isRealTimeRate !== undefined && (
                                            msg.transactionData.isRealTimeRate ? (
                                                <div className="relative group">
                                                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse block"></span>
                                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-32 bg-gray-900 text-white text-[10px] p-1.5 rounded text-center z-10">
                                                        {t('Live Real-time Rate')}
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="relative group">
                                                    <AlertCircle className="w-3 h-3 text-yellow-500" />
                                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-32 bg-gray-900 text-white text-[10px] p-1.5 rounded text-center z-10">
                                                        {t('Estimated Fallback Rate')}
                                                    </div>
                                                </div>
                                            )
                                        )}
                                        <TrendingUp className="w-4 h-4 text-celo-green" />
                                        <span className="text-sm font-bold text-gray-800 dark:text-gray-200">
                                            1 {msg.transactionData.currency} = {msg.transactionData.exchangeRate || '...'} {msg.transactionData.recipientCurrency}
                                        </span>
                                    </div>

                                    {/* Editable Frequency & Date */}
                                    <div className="bg-gray-50 dark:bg-gray-800/50 p-3 rounded-xl border border-gray-100 dark:border-gray-700 space-y-3">
                                        <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider flex items-center gap-1">
                                            <CalendarClock className="w-3 h-3" />
                                            {t('Payment Schedule')}
                                        </label>
                                        <div className="grid grid-cols-2 gap-2">
                                            <select
                                                value={msg.transactionData.frequency || 'one-time'}
                                                onChange={(e) => updateTransactionData(msg.id, { frequency: e.target.value })}
                                                className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white text-sm rounded-lg block w-full p-2 outline-none focus:ring-1 focus:ring-celo-green"
                                            >
                                                <option value="one-time">{t('One-time')}</option>
                                                <option value="daily">{t('Daily')}</option>
                                                <option value="weekly">{t('Weekly')}</option>
                                                <option value="monthly">{t('Monthly')}</option>
                                            </select>
                                            
                                            <input
                                                type="date"
                                                value={msg.transactionData.startDate || ''}
                                                disabled={!msg.transactionData.frequency || msg.transactionData.frequency === 'one-time'}
                                                onChange={(e) => updateTransactionData(msg.id, { startDate: e.target.value })}
                                                className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white text-sm rounded-lg block w-full p-2 outline-none focus:ring-1 focus:ring-celo-green disabled:opacity-50"
                                            />
                                        </div>
                                    </div>

                                    {/* Detailed Breakdown with Expandable Fees */}
                                    <div className="space-y-2 text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-gray-100 dark:border-gray-600">
                                        <div className="flex justify-between">
                                            <span>{t('Mento Protocol Status')}</span>
                                            <span className="text-green-600 dark:text-green-400 font-medium flex items-center gap-1">
                                                <Zap className="w-3 h-3" /> {t('Optimal')}
                                            </span>
                                        </div>
                                        
                                        <div className="flex flex-col">
                                            <div 
                                                className="flex justify-between cursor-pointer hover:text-gray-700 dark:hover:text-gray-200"
                                                onClick={() => setExpandedFees(expandedFees === msg.id ? null : msg.id)}
                                            >
                                                <div className="flex items-center gap-1">
                                                    <span>{t('Total Network Fees')}</span>
                                                    <Info className="w-3 h-3" />
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <span className="font-medium text-gray-700 dark:text-gray-300">${msg.transactionData.fees}</span>
                                                    <ChevronDown className={`w-3 h-3 transition-transform ${expandedFees === msg.id ? 'rotate-180' : ''}`} />
                                                </div>
                                            </div>
                                            
                                            {expandedFees === msg.id && msg.transactionData.feeBreakdown && (
                                                <div className="mt-2 pl-2 border-l-2 border-gray-200 dark:border-gray-600 space-y-1 animate-fade-in-up">
                                                    <div className="flex justify-between text-[10px]">
                                                        <span>{t('Mento Swap Fee')}</span>
                                                        <span>${msg.transactionData.feeBreakdown.mentoFee}</span>
                                                    </div>
                                                    <div className="flex justify-between text-[10px]">
                                                        <span>{t('Celo Gas Fee')}</span>
                                                        <span>${msg.transactionData.feeBreakdown.networkFee}</span>
                                                    </div>
                                                    <div className="flex justify-between text-[10px]">
                                                        <span>{t('Secure Enclave (TEE)')}</span>
                                                        <span>${msg.transactionData.feeBreakdown.securityFee}</span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        <div className="flex justify-between">
                                            <span>{t('Est. Arrival')}</span>
                                            <span className="font-medium text-gray-700 dark:text-gray-300">
                                                {msg.transactionData.frequency === 'one-time' ? t('< 5 seconds') : t('Scheduled')}
                                            </span>
                                        </div>
                                    </div>

                                    <button 
                                        onClick={() => handleConfirm(msg.id)}
                                        className="w-full py-3 bg-celo-green hover:bg-green-500 text-white font-bold rounded-xl transition-all active:scale-95 shadow-lg shadow-green-500/20"
                                    >
                                        {msg.transactionData.frequency && msg.transactionData.frequency !== 'one-time' ? t('Schedule Payment') : t('Confirm Transfer')}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Success State */}
                        {msg.role === 'assistant' && msg.type === 'transaction_success' && (
                             <div className="bg-green-50 dark:bg-green-900/10 rounded-2xl border border-green-100 dark:border-green-800 p-6 flex flex-col items-center text-center animate-fade-in-up">
                                <div className="w-12 h-12 bg-green-500 rounded-full flex items-center justify-center mb-3 text-white shadow-lg shadow-green-500/20">
                                    <CheckCircle2 className="w-6 h-6" />
                                </div>
                                <h4 className="text-green-900 dark:text-green-400 font-bold text-lg">
                                    {msg.transactionData?.frequency && msg.transactionData.frequency !== 'one-time' ? t('Payment Scheduled!') : t('Transaction Sent!')}
                                </h4>
                                <p className="text-green-700 dark:text-green-300 text-sm mt-1">
                                    {msg.transactionData?.frequency && msg.transactionData.frequency !== 'one-time'
                                        ? t('{{amount}} {{currency}} will be sent to {{recipient}} {{frequency}} starting {{startDate}}.', {
                                            amount: msg.transactionData?.convertedAmount || '',
                                            currency: msg.transactionData?.recipientCurrency || '',
                                            recipient: msg.transactionData?.recipient || '',
                                            frequency: msg.transactionData?.frequency || '',
                                            startDate: msg.transactionData?.startDate || '',
                                          })
                                        : t('{{amount}} {{currency}} is on its way to {{recipient}}.', {
                                            amount: msg.transactionData?.convertedAmount || '',
                                            currency: msg.transactionData?.recipientCurrency || '',
                                            recipient: msg.transactionData?.recipient || '',
                                          })
                                    }
                                </p>

                                {/* Signer badge */}
                                {msg.transactionData?.signerType && (
                                    <div className={`mt-2 px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1.5 ${
                                        msg.transactionData.signerType === 'user'
                                            ? 'bg-celo-green/10 text-celo-green'
                                            : 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                                    }`}>
                                        <Wallet className="w-3 h-3" />
                                        {msg.transactionData.signerType === 'user' ? t('Signed by your wallet') : t('Signed by agent wallet')}
                                    </div>
                                )}

                                {/* Tx hash row */}
                                {msg.transactionData?.txHash && (
                                    <div className="mt-2 text-xs text-gray-400 font-mono">
                                        {msg.transactionData.txHash.slice(0, 10)}…{msg.transactionData.txHash.slice(-8)}
                                    </div>
                                )}
                                
                                <div className="flex gap-2 mt-4 w-full">
                                    <a
                                        href={msg.transactionData?.explorerUrl || '#'}
                                        target={msg.transactionData?.explorerUrl ? '_blank' : undefined}
                                        rel="noopener noreferrer"
                                        className="flex-1 py-2 text-xs font-bold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg flex items-center justify-center bg-white dark:bg-gray-800"
                                    >
                                        {t('View on CeloScan')}
                                    </a>
                                    <button 
                                        onClick={() => handleShare(msg)}
                                        className="flex-1 py-2 text-xs font-bold text-green-700 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 border border-green-200 dark:border-green-800 rounded-lg flex items-center justify-center gap-1 bg-green-50 dark:bg-green-900/20"
                                    >
                                        <Share2 className="w-3 h-3" />
                                        {t('Share')}
                                    </button>
                                </div>
                             </div>
                        )}
                    </div>
                </div>
            ))}
            {/* LLM Status Indicator */}
            {isStreaming && (
              <LLMStatusIndicator status={llmStatus} className="pl-2" />
            )}
            {isLoading && (
                 <div className="flex items-center gap-2 text-gray-400 text-sm pl-2 animate-pulse">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('Processing request...')}</span>
                 </div>
            )}
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700 relative z-10 shrink-0">
            {messages.length < 3 && !isLoading && (
                <div className="flex gap-2 overflow-x-auto pb-3 scrollbar-hide">
                    {SUGGESTED_PROMPTS.map((prompt, i) => (
                        <button 
                            key={i}
                            onClick={() => handleSend(prompt)}
                            className="whitespace-nowrap px-3 py-1.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-xs text-gray-600 dark:text-gray-300 hover:border-celo-green hover:text-celo-green transition-colors"
                        >
                            {t(prompt)}
                        </button>
                    ))}
                </div>
            )}
            {isConnected && (
                <button
                    onClick={() => setShowQuickTransfer(true)}
                    className="w-full mb-2 py-2 flex items-center justify-center gap-2 bg-celo-green/10 hover:bg-celo-green/20 border border-celo-green/30 text-celo-green font-semibold rounded-xl text-sm transition-all"
                    title={t('Send directly from your connected wallet')}
                >
                    <Wallet className="w-4 h-4" />
                    {t('Send with Your Wallet')}
                </button>
            )}
            <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-700 rounded-xl p-2 border border-gray-200 dark:border-gray-600 focus-within:border-celo-green focus-within:ring-2 focus-within:ring-green-500/10 transition-all">
                <button
                    onClick={toggleListening}
                    className={`p-2 rounded-lg transition-all ${isListening ? 'bg-red-500 text-white animate-pulse' : 'text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'}`}
                    title={t('Speak to CeloFlow')}
                >
                    <Mic className="w-4 h-4" />
                </button>
                <input 
                    type="text" 
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder={isListening ? t('Listening...') : t('Type a command...')}
                    className="flex-1 bg-transparent border-none outline-none text-gray-800 dark:text-white placeholder-gray-400 text-sm px-2"
                    disabled={isLoading}
                />
                <button 
                    onClick={() => handleSend()}
                    disabled={!input.trim() || isLoading}
                    className="p-2 bg-gray-900 dark:bg-celo-green text-white rounded-lg hover:bg-gray-800 dark:hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    <Send className="w-4 h-4" />
                </button>
            </div>
        </div>

        {/* Quick Transfer Modal */}
        <QuickTransferModal
          isOpen={showQuickTransfer}
          onClose={() => setShowQuickTransfer(false)}
          onTransferComplete={handleQuickTransferComplete}
        />

        {/* Transfer Preview Modal (two-step TEE flow) */}
        {showTransferPreview && transferPreviewData && (
          <TransferPreviewModal
            previewData={transferPreviewData}
            onConfirm={handlePreviewConfirm}
            onCancel={handlePreviewCancel}
            isExecuting={isExecutingPreview}
          />
        )}

        {/* Wallet Authorization Modal */}
        <WalletAuthorizationModal
          isOpen={showWalletAuth}
          onClose={handleCloseWalletAuth}
          preparedTransfer={userSigning.preparedTransfer}
          signingStep={userSigning.step}
          error={userSigning.error}
          isLoading={userSigning.isLoading}
          onChooseTEE={handleChooseTEE}
          onChooseUserWallet={handleChooseUserWallet}
          onRetryWithTEE={handleRetryWithTEE}
        />
    </div>
  );
};