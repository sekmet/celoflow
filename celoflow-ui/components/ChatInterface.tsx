import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, CheckCircle2, ChevronRight, Loader2, RefreshCcw, History, CalendarClock, X, Search, Activity, Zap, TrendingUp, AlertCircle, Mic, ChevronDown, Info, Ban, Share2, HelpCircle } from 'lucide-react';
import { parseUserMessage } from '../services/geminiService';
import { getExchangeRate } from '../services/currencyService';
import { Message, TransactionIntent, TransactionHistoryItem } from '../types';
import { SUGGESTED_PROMPTS, SUPPORTED_CURRENCIES } from '../constants';

interface ChatInterfaceProps {
  className?: string;
  fullScreen?: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '', fullScreen = false }) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hi! I\'m CeloFlow. I can help you send money globally using the Celo blockchain. Where would you like to send money today?',
      type: 'text'
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<TransactionHistoryItem[]>([]);
  const [historySearch, setHistorySearch] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [userCurrency, setUserCurrency] = useState('USD');
  const [localEstimates, setLocalEstimates] = useState<Record<string, { source: string, target: string }>>({});
  const [expandedFees, setExpandedFees] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, expandedFees]); // Scroll when fees expand too

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

  // Initialize Speech Recognition
  useEffect(() => {
    if (typeof window !== 'undefined') {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRecognition) {
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false;
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = 'en-US';

            recognitionRef.current.onstart = () => setIsListening(true);
            recognitionRef.current.onend = () => setIsListening(false);
            recognitionRef.current.onerror = (event: any) => {
                console.error('Speech recognition error', event.error);
                setIsListening(false);
            };
            
            recognitionRef.current.onresult = (event: any) => {
                const transcript = event.results[0][0].transcript;
                setInput(prev => {
                    const spacer = prev.length > 0 && !prev.endsWith(' ') ? ' ' : '';
                    return prev + spacer + transcript;
                });
            };
        }
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
        alert("Voice input is not supported in this browser. Please use Chrome, Edge, or Safari.");
        return;
    }
    if (isListening) {
        recognitionRef.current.stop();
    } else {
        recognitionRef.current.start();
    }
  };

  const handleSend = async (text: string = input) => {
    if (!text.trim()) return;

    // Add User Message
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    // Call Gemini
    const result = await parseUserMessage(text);

    setIsLoading(false);

    // Add Assistant Message
    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: result.text,
      type: result.transaction ? 'transaction_preview' : 'text',
      transactionData: result.transaction
    };

    setMessages(prev => [...prev, assistantMsg]);
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
    // Generate a unique history ID
    const historyId = Date.now().toString();

    setMessages(prev => {
        const updated = prev.map(msg => {
            if (msg.id === transactionId && msg.type === 'transaction_preview' && msg.transactionData) {
                
                // Determine initial status
                const isRecurring = msg.transactionData.frequency && msg.transactionData.frequency !== 'one-time';
                const initialStatus: TransactionHistoryItem['status'] = isRecurring ? 'scheduled' : 'processing';

                // Add to history with processing/scheduled status
                const historyItem: TransactionHistoryItem = {
                    id: historyId,
                    date: new Date().toLocaleDateString(),
                    intent: msg.transactionData,
                    status: initialStatus
                };
                setHistory(h => [historyItem, ...h]);
                
                // If it's a one-time transaction, simulate processing -> completed
                if (!isRecurring) {
                    setTimeout(() => {
                        setHistory(currentHistory => currentHistory.map(item => 
                            item.id === historyId && item.status !== 'cancelled'
                                ? { ...item, status: 'completed' } 
                                : item
                        ));
                    }, 4000); // 4 second delay to simulate blockchain confirmation
                }
                
                return { ...msg, type: 'transaction_success' as const };
            }
            return msg;
        });
        return updated;
    });
  };

  const handleCancelTransaction = (historyId: string) => {
      if (window.confirm("Are you sure you want to cancel this scheduled payment?")) {
          setHistory(prev => prev.map(item => 
              item.id === historyId ? { ...item, status: 'cancelled' } : item
          ));
      }
  };

  const handleShare = async (msg: Message) => {
      const data = msg.transactionData;
      if (!data) return;

      const shareData = {
          title: 'CeloFlow Transaction',
          text: `I just sent ${data.amount} ${data.currency} to ${data.recipient} via CeloFlow!`,
          url: window.location.href
      };

      try {
          if (navigator.share) {
              await navigator.share(shareData);
          } else {
              await navigator.clipboard.writeText(shareData.text);
              alert("Transaction details copied to clipboard!");
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
              tooltip: 'Funds have successfully reached the recipient.'
          };
          case 'processing': return {
              class: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
              tooltip: 'Transaction is currently being confirmed on the blockchain.'
          };
          case 'scheduled': return {
              class: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
              tooltip: 'Payment is set to execute at a future date.'
          };
          case 'cancelled': return {
              class: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-400',
              tooltip: 'This transaction was cancelled by the user.'
          };
          case 'failed': return {
              class: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
              tooltip: 'Transaction could not be completed. Please try again.'
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
                        <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">Online</span>
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-1">
                <button 
                    onClick={() => setShowHistory(!showHistory)}
                    className={`p-2 rounded-full transition-colors ${showHistory ? 'bg-celo-green text-white' : 'hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-400'}`}
                    title="Transaction History"
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
                    <h3 className="font-bold text-lg text-gray-900 dark:text-white">Recent Activity</h3>
                    <button onClick={() => setShowHistory(false)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full">
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                <div className="mb-4 relative">
                    <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search recipient or currency..."
                        value={historySearch}
                        onChange={(e) => setHistorySearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg text-sm outline-none focus:ring-2 focus:ring-celo-green placeholder-gray-500 dark:placeholder-gray-400"
                    />
                </div>

                {filteredHistory.length === 0 ? (
                    <div className="text-center text-gray-400 mt-10">
                        {history.length === 0 ? "No transactions yet." : "No matching transactions."}
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
                                                    title="Cancel Scheduled Payment"
                                                >
                                                    <Ban className="w-4 h-4" />
                                                </button>
                                            )}
                                            <div className="relative group">
                                                <div className={`px-2 py-1 rounded text-[10px] font-bold uppercase flex items-center gap-1 cursor-help ${statusConfig.class}`}>
                                                    {item.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin" />}
                                                    {item.status}
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
                                            <span className="text-gray-500 text-xs uppercase tracking-wider">Sent</span>
                                            <span className="font-medium text-gray-900 dark:text-white">{item.intent.amount} {item.intent.currency}</span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span className="text-gray-500 text-xs uppercase tracking-wider">Received</span>
                                            <span className="font-bold text-celo-green">{item.intent.convertedAmount} {item.intent.recipientCurrency}</span>
                                        </div>
                                    </div>

                                    {item.intent.frequency && item.intent.frequency !== 'one-time' && (
                                         <div className="mt-3 text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1 bg-blue-50 dark:bg-blue-900/20 p-2 rounded-lg">
                                             <CalendarClock className="w-3 h-3" />
                                             {item.intent.frequency} starting {item.intent.startDate}
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
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-6 bg-gray-50/50 dark:bg-gray-900/50 scroll-smooth">
            {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`}>
                    <div className={`max-w-[90%] ${msg.role === 'user' ? 'order-1' : 'order-2'}`}>
                        {/* Avatar */}
                        {msg.role === 'assistant' && msg.type === 'text' && (
                             <div className="text-sm bg-white dark:bg-gray-700 dark:text-gray-100 p-4 rounded-2xl rounded-tl-none shadow-sm text-gray-700 border border-gray-100 dark:border-gray-600">
                                {msg.content}
                             </div>
                        )}

                        {msg.role === 'user' && (
                             <div className="text-sm bg-gray-900 dark:bg-celo-green text-white p-4 rounded-2xl rounded-tr-none shadow-md">
                                {msg.content}
                             </div>
                        )}

                        {/* Transaction Card */}
                        {msg.role === 'assistant' && msg.type === 'transaction_preview' && msg.transactionData && (
                            <div className="bg-white dark:bg-gray-700 rounded-2xl shadow-lg border border-gray-100 dark:border-gray-600 overflow-hidden transform transition-all">
                                <div className="p-4 border-b border-gray-50 dark:border-gray-600 bg-gray-50/50 dark:bg-gray-800/30">
                                    <p className="text-sm text-gray-600 dark:text-gray-300 mb-1">{msg.content}</p>
                                    <div className="flex items-center justify-between mt-3">
                                        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Best Quote Found</span>
                                        <div className="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1">
                                            <CheckCircle2 className="w-3 h-3" />
                                            Saved ${msg.transactionData.savings.toFixed(2)}
                                        </div>
                                    </div>
                                </div>
                                <div className="p-5 space-y-4">
                                    <div className="flex justify-between items-center">
                                        <div className="flex-1">
                                            <p className="text-xs text-gray-400 mb-1">You Send</p>
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
                                            <p className="text-xs text-gray-400 mb-1">{msg.transactionData.recipient} Receives</p>
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
                                                        Live Real-time Rate
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="relative group">
                                                    <AlertCircle className="w-3 h-3 text-yellow-500" />
                                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-32 bg-gray-900 text-white text-[10px] p-1.5 rounded text-center z-10">
                                                        Estimated Fallback Rate
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
                                            Payment Schedule
                                        </label>
                                        <div className="grid grid-cols-2 gap-2">
                                            <select
                                                value={msg.transactionData.frequency || 'one-time'}
                                                onChange={(e) => updateTransactionData(msg.id, { frequency: e.target.value })}
                                                className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-gray-900 dark:text-white text-sm rounded-lg block w-full p-2 outline-none focus:ring-1 focus:ring-celo-green"
                                            >
                                                <option value="one-time">One-time</option>
                                                <option value="daily">Daily</option>
                                                <option value="weekly">Weekly</option>
                                                <option value="monthly">Monthly</option>
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
                                            <span>Mento Protocol Status</span>
                                            <span className="text-green-600 dark:text-green-400 font-medium flex items-center gap-1">
                                                <Zap className="w-3 h-3" /> Optimal
                                            </span>
                                        </div>
                                        
                                        <div className="flex flex-col">
                                            <div 
                                                className="flex justify-between cursor-pointer hover:text-gray-700 dark:hover:text-gray-200"
                                                onClick={() => setExpandedFees(expandedFees === msg.id ? null : msg.id)}
                                            >
                                                <div className="flex items-center gap-1">
                                                    <span>Total Network Fees</span>
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
                                                        <span>Mento Swap Fee</span>
                                                        <span>${msg.transactionData.feeBreakdown.mentoFee}</span>
                                                    </div>
                                                    <div className="flex justify-between text-[10px]">
                                                        <span>Celo Gas Fee</span>
                                                        <span>${msg.transactionData.feeBreakdown.networkFee}</span>
                                                    </div>
                                                    <div className="flex justify-between text-[10px]">
                                                        <span>Secure Enclave (TEE)</span>
                                                        <span>${msg.transactionData.feeBreakdown.securityFee}</span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>

                                        <div className="flex justify-between">
                                            <span>Est. Arrival</span>
                                            <span className="font-medium text-gray-700 dark:text-gray-300">
                                                {msg.transactionData.frequency === 'one-time' ? '< 5 seconds' : 'Scheduled'}
                                            </span>
                                        </div>
                                    </div>

                                    <button 
                                        onClick={() => handleConfirm(msg.id)}
                                        className="w-full py-3 bg-celo-green hover:bg-green-500 text-white font-bold rounded-xl transition-all active:scale-95 shadow-lg shadow-green-500/20"
                                    >
                                        {msg.transactionData.frequency && msg.transactionData.frequency !== 'one-time' ? 'Schedule Payment' : 'Confirm Transfer'}
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
                                    {msg.transactionData?.frequency && msg.transactionData.frequency !== 'one-time' ? 'Payment Scheduled!' : 'Transaction Sent!'}
                                </h4>
                                <p className="text-green-700 dark:text-green-300 text-sm mt-1">
                                    {msg.transactionData?.convertedAmount} {msg.transactionData?.recipientCurrency} 
                                    {msg.transactionData?.frequency && msg.transactionData.frequency !== 'one-time' 
                                        ? ` will be sent to ${msg.transactionData?.recipient} ${msg.transactionData.frequency} starting ${msg.transactionData.startDate}.`
                                        : ` is on its way to ${msg.transactionData?.recipient}.`
                                    }
                                </p>
                                
                                <div className="flex gap-2 mt-4 w-full">
                                    <a href="#" className="flex-1 py-2 text-xs font-bold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-lg flex items-center justify-center bg-white dark:bg-gray-800">
                                        View on CeloScan
                                    </a>
                                    <button 
                                        onClick={() => handleShare(msg)}
                                        className="flex-1 py-2 text-xs font-bold text-green-700 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300 border border-green-200 dark:border-green-800 rounded-lg flex items-center justify-center gap-1 bg-green-50 dark:bg-green-900/20"
                                    >
                                        <Share2 className="w-3 h-3" />
                                        Share
                                    </button>
                                </div>
                             </div>
                        )}
                    </div>
                </div>
            ))}
            {isLoading && (
                 <div className="flex items-center gap-2 text-gray-400 text-sm pl-2 animate-pulse">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Processing request...</span>
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
                            {prompt}
                        </button>
                    ))}
                </div>
            )}
            <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-700 rounded-xl p-2 border border-gray-200 dark:border-gray-600 focus-within:border-celo-green focus-within:ring-2 focus-within:ring-green-500/10 transition-all">
                <button
                    onClick={toggleListening}
                    className={`p-2 rounded-lg transition-all ${isListening ? 'bg-red-500 text-white animate-pulse' : 'text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'}`}
                    title="Speak to CeloFlow"
                >
                    <Mic className="w-4 h-4" />
                </button>
                <input 
                    type="text" 
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder={isListening ? "Listening..." : "Type a command..."}
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
    </div>
  );
};