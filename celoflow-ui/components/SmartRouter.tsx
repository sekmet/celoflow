import React from 'react';
import { ArrowRight, Zap, RefreshCw, ShieldCheck } from 'lucide-react';
import { useI18n } from '../lib/language';

export const SmartRouter: React.FC = () => {
  const { t } = useI18n();

  return (
    <div className="w-full bg-[#0F1115] text-white py-20 overflow-hidden relative">
        {/* Background Gradients */}
        <div className="absolute top-0 left-0 w-1/2 h-full bg-green-500/5 blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-1/2 h-full bg-blue-500/5 blur-[120px]" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
            <div className="grid lg:grid-cols-2 gap-16 items-center">
                
                {/* Text Content */}
                <div className="space-y-8">
                    <div className="inline-flex items-center space-x-2 bg-white/10 px-4 py-1.5 rounded-full border border-white/10">
                        <span className="w-2 h-2 rounded-full bg-celo-green animate-pulse" />
                        <span className="text-sm font-medium text-celo-green">{t('Smart Agent v2.1')}</span>
                    </div>
                    
                    <h2 className="text-4xl md:text-5xl font-display font-bold leading-tight">
                        {t('AI that thinks like a')} <br/>
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-celo-green to-teal-400">{t('Market Maker.')}</span>
                    </h2>
                    
                    <p className="text-gray-400 text-lg leading-relaxed">
                        {t('CeloFlow scans decentralized exchanges (DEXs) and the Mento Protocol in real-time to find liquidity pools with the lowest slippage, ensuring your family gets the most out of every dollar sent.')}
                    </p>

                    <div className="grid grid-cols-3 gap-6 pt-8 border-t border-white/10">
                        <div>
                            <div className="text-3xl font-bold text-white mb-1">0.02%</div>
                            <div className="text-sm text-gray-500">{t('Slippage')}</div>
                        </div>
                        <div>
                            <div className="text-3xl font-bold text-white mb-1">1.2s</div>
                            <div className="text-sm text-gray-500">{t('Route Time')}</div>
                        </div>
                        <div>
                            <div className="text-3xl font-bold text-celo-green mb-1">$4.20</div>
                            <div className="text-sm text-gray-500">{t('Avg. Savings')}</div>
                        </div>
                    </div>
                </div>

                {/* Router Visualization */}
                <div className="relative">
                    <div className="dark-glass rounded-3xl p-8 shadow-2xl border border-gray-800">
                        <div className="flex justify-between items-center mb-8">
                            <span className="text-xs font-semibold tracking-wider text-gray-500 uppercase">{t('Route Optimization')}</span>
                            <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400">{t('Active')}</span>
                        </div>

                        {/* Flow Diagram */}
                        <div className="flex items-center justify-between relative py-12">
                            {/* Line */}
                            <div className="absolute top-1/2 left-0 w-full h-0.5 bg-gray-800 -z-10"></div>
                            
                            {/* Animated Line */}
                            <div className="absolute top-1/2 left-0 h-0.5 bg-gradient-to-r from-celo-green to-blue-500 -z-10 w-[0%] animate-[grow_3s_infinite_ease-out]"></div>

                            {/* Node 1: Sender */}
                            <div className="flex flex-col items-center gap-3">
                                <div className="w-16 h-16 rounded-2xl bg-[#1C1E21] border border-gray-700 flex items-center justify-center shadow-lg relative z-10 group hover:border-celo-green transition-colors">
                                    <span className="font-bold text-white">cUSD</span>
                                </div>
                                <span className="text-sm text-gray-400">{t('Stablecoin')}</span>
                            </div>

                             {/* Step 1 */}
                             <div className="flex flex-col items-center gap-2">
                                <div className="px-3 py-1 bg-blue-900/30 rounded border border-blue-500/30 text-[10px] text-blue-300">
                                    Uniswap V3
                                </div>
                                <ArrowRight className="w-4 h-4 text-gray-600" />
                             </div>

                             {/* Node 2: Bridge */}
                             <div className="flex flex-col items-center gap-3">
                                <div className="w-14 h-14 rounded-full bg-[#1C1E21] border border-gray-700 flex items-center justify-center shadow-lg relative z-10">
                                    <RefreshCw className="w-6 h-6 text-blue-400 animate-spin-slow" style={{ animationDuration: '3s' }}/>
                                </div>
                                <span className="text-sm text-gray-400">Mento</span>
                            </div>

                            {/* Step 2 */}
                             <div className="flex flex-col items-center gap-2">
                                <div className="px-3 py-1 bg-green-900/30 rounded border border-green-500/30 text-[10px] text-green-300">
                                    TEE Secure
                                </div>
                                <ArrowRight className="w-4 h-4 text-gray-600" />
                             </div>

                             {/* Node 3: Local */}
                             <div className="flex flex-col items-center gap-3">
                                <div className="w-16 h-16 rounded-2xl bg-[#1C1E21] border border-gray-700 flex items-center justify-center shadow-lg relative z-10 hover:border-celo-green transition-colors">
                                    <span className="font-bold text-celo-green">cKES</span>
                                </div>
                                <span className="text-sm text-gray-400">{t('Local')}</span>
                            </div>

                        </div>

                        <div className="mt-6 p-4 rounded-xl bg-gray-800/50 border border-gray-700 flex items-start gap-3">
                             <ShieldCheck className="w-5 h-5 text-celo-green shrink-0 mt-0.5" />
                             <div className="text-sm">
                                <p className="text-white font-medium">{t('TEE Verification Complete')}</p>
                                <p className="text-gray-500">{t('Key management is handled inside a secure enclave. You never touch a private key.')}</p>
                             </div>
                        </div>
                    </div>
                    
                    {/* Decorative floating elements */}
                    <div className="absolute -top-10 -right-10 w-20 h-20 bg-celo-green rounded-full blur-2xl opacity-20 animate-pulse"></div>
                </div>
            </div>
        </div>
        
        <style>{`
            @keyframes grow {
                0% { width: 0%; opacity: 0; }
                50% { opacity: 1; }
                100% { width: 100%; opacity: 0; }
            }
        `}</style>
    </div>
  );
};
