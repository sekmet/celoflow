import React, { useState, useEffect } from 'react';
import { WagmiProvider } from 'wagmi';
import { QueryClientProvider } from '@tanstack/react-query';
import { Bot, ChevronRight, Globe, Lock, Wallet, Zap, CheckCircle2, Moon, Sun, ArrowLeft, Users } from 'lucide-react';
import { ChatInterface } from './components/ChatInterface';
import { SmartRouter } from './components/SmartRouter';
import { WalletConnect } from './components/WalletConnect';
import { config, queryClient } from './lib/wagmi-config';
import { ContactsManager } from './components/ContactsManager';
import { LanguageSwitcher } from './components/LanguageSwitcher';
import { NAV_LINKS } from './constants';

function AppContent() {
  const [isDark, setIsDark] = useState(false);
  const [currentView, setCurrentView] = useState<'landing' | 'app'>('landing');
  const [showContacts, setShowContacts] = useState(false);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  if (currentView === 'app') {
    return (
      <div className="min-h-screen flex flex-col font-sans bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
        <nav className="sticky top-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 transition-colors duration-300">
            <div className="flex items-center gap-2 cursor-pointer group" onClick={() => setCurrentView('landing')}>
              <div className="p-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 group-hover:bg-gray-200 dark:group-hover:bg-gray-700 transition-colors">
                 <ArrowLeft className="w-5 h-5" />
              </div>
              <span className="font-display font-bold text-xl tracking-tight text-gray-900 dark:text-white group-hover:opacity-80 transition-opacity">CeloFlow</span>
            </div>
            <div className="flex items-center gap-3">
                 <button
                    onClick={() => setShowContacts(true)}
                    className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
                    title="Contacts"
                 >
                    <Users className="w-5 h-5" />
                 </button>
                 <LanguageSwitcher />
                 <WalletConnect />
                 <button 
                    onClick={() => setIsDark(!isDark)}
                    className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
                >
                    {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </button>
            </div>
        </nav>
        <div className="flex-1 flex relative overflow-hidden">
             {/* Background Decoration for App View */}
             <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-green-400/10 dark:bg-green-500/5 rounded-full blur-3xl animate-pulse-slow"></div>
                <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-400/10 dark:bg-blue-500/5 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }}></div>
             </div>
             
             <div className="w-full min-h-full relative z-10 animate-fade-in-up">
                <ChatInterface fullScreen={true} />
             </div>
        </div>
        {showContacts && <ContactsManager onClose={() => setShowContacts(false)} />}
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col font-sans text-gray-900 dark:text-white bg-white dark:bg-gray-900 transition-colors duration-300 overflow-x-hidden">
      
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-100 dark:border-gray-800 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
              <div className="w-8 h-8 bg-black dark:bg-celo-green rounded-lg flex items-center justify-center text-white">
                <Zap className="w-5 h-5 fill-current" />
              </div>
              <span className="font-display font-bold text-xl tracking-tight text-gray-900 dark:text-white">CeloFlow</span>
            </div>
            
            <div className="hidden md:flex items-center space-x-8">
              {NAV_LINKS.map(link => (
                <a key={link.name} href={link.href} className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white transition-colors">
                  {link.name}
                </a>
              ))}
            </div>

            <div className="flex items-center gap-3">
                <WalletConnect />
                <button 
                    onClick={() => setIsDark(!isDark)}
                    className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
                >
                    {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                </button>
                <button 
                    onClick={() => setCurrentView('app')}
                    className="bg-black dark:bg-white text-white dark:text-black px-5 py-2 rounded-full text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors flex items-center gap-2"
                >
                    Launch App
                    <ChevronRight className="w-4 h-4" />
                </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="flex-1 pt-16">
        
        {/* Hero Section */}
        <section className="relative bg-white dark:bg-gray-900 overflow-hidden transition-colors duration-300">
            {/* Background Decorations */}
            <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-green-50 dark:bg-green-900/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4 opacity-50 pointer-events-none"></div>
            
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-24 lg:pt-24 lg:pb-32 relative">
                <div className="grid lg:grid-cols-2 gap-12 lg:gap-8 items-center">
                    
                    {/* Hero Content */}
                    <div className="max-w-2xl">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 text-xs font-bold mb-6 tracking-wide">
                            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                            SMART AGENT LIVE
                        </div>
                        <h1 className="text-5xl lg:text-7xl font-display font-bold tracking-tight text-gray-900 dark:text-white leading-[1.1] mb-6">
                            Send Money Like <br/>
                            You Send a <span className="text-celo-green">Message</span>
                        </h1>
                        <p className="text-lg text-gray-600 dark:text-gray-400 mb-8 leading-relaxed max-w-lg">
                            The financial agent that turns your words into instant global transfers on the Celo blockchain. Simple, secure, and fast.
                        </p>
                        
                        <div className="flex flex-col sm:flex-row gap-4">
                            <button 
                                onClick={() => setCurrentView('app')}
                                className="px-8 py-4 bg-celo-green text-white font-bold rounded-full hover:bg-green-500 transition-all shadow-xl shadow-green-500/20 active:scale-95 flex items-center justify-center gap-2"
                            >
                                Try CeloFlow Now
                                <Bot className="w-5 h-5" />
                            </button>
                            <button className="px-8 py-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 font-bold rounded-full hover:bg-gray-50 dark:hover:bg-gray-700 transition-all flex items-center justify-center">
                                View Activity
                            </button>
                        </div>

                        <div className="mt-8 flex items-center gap-4">
                            <div className="flex -space-x-3">
                                {[1,2,3].map(i => (
                                    <img key={i} src={`https://picsum.photos/40/40?random=${i}`} className="w-10 h-10 rounded-full border-2 border-white dark:border-gray-900" alt="User" />
                                ))}
                            </div>
                            <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">Trusted by 10,000+ early users</p>
                        </div>
                    </div>

                    {/* Hero Interactive Demo */}
                    <div className="relative">
                        <div className="absolute -inset-4 bg-gradient-to-r from-green-500 to-blue-500 rounded-[2.5rem] blur-lg opacity-20 animate-pulse-slow"></div>
                        <ChatInterface />
                        
                        {/* Floating Tooltip */}
                        <div className="absolute top-20 -right-4 lg:-right-12 bg-white dark:bg-gray-800 rounded-xl shadow-xl p-3 flex items-center gap-3 animate-float hidden sm:flex border border-gray-100 dark:border-gray-700">
                             <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center text-green-600 dark:text-green-400">
                                <CheckCircle2 className="w-6 h-6" />
                             </div>
                             <div>
                                <p className="text-xs text-gray-500 dark:text-gray-400">Just Saved</p>
                                <p className="font-bold text-gray-900 dark:text-white">$3.50 vs Bank</p>
                             </div>
                        </div>
                    </div>

                </div>
            </div>
        </section>

        {/* Features / Why Celo */}
        <section id="features" className="py-24 bg-gray-50 dark:bg-gray-800/50 transition-colors duration-300">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center max-w-3xl mx-auto mb-16">
                    <h2 className="text-3xl font-display font-bold text-gray-900 dark:text-white mb-4">Built for the Real World</h2>
                    <p className="text-gray-600 dark:text-gray-400">CeloFlow leverages advanced blockchain infrastructure to make money move as freely as information.</p>
                </div>

                <div className="grid md:grid-cols-3 gap-8">
                    {[
                        {
                            icon: <Globe className="w-6 h-6 text-blue-500" />,
                            title: "Mento Protocol",
                            desc: "Seamlessly swaps stablecoins (cUSD, cEUR, cREAL) with minimal slippage using decentralized stability mechanisms."
                        },
                        {
                            icon: <Lock className="w-6 h-6 text-green-500" />,
                            title: "TEE Security",
                            desc: "Your keys are managed in a Trusted Execution Environment. You authenticate; the enclave signs. No seed phrases to lose."
                        },
                        {
                            icon: <Wallet className="w-6 h-6 text-purple-500" />,
                            title: "Gas Abstraction",
                            desc: "Pay transaction fees in the same currency you send. No need to hold CELO just to pay for gas."
                        }
                    ].map((feature, i) => (
                        <div key={i} className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 hover:shadow-md transition-all">
                            <div className="w-12 h-12 rounded-xl bg-gray-50 dark:bg-gray-700 flex items-center justify-center mb-6">
                                {feature.icon}
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">{feature.title}</h3>
                            <p className="text-gray-600 dark:text-gray-400 leading-relaxed">
                                {feature.desc}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </section>

        {/* Smart Router Dark Section */}
        <section id="how-it-works">
            <SmartRouter />
        </section>

        {/* CTA Section */}
        <section className="py-24 bg-white dark:bg-gray-900 relative overflow-hidden transition-colors duration-300">
             <div className="max-w-4xl mx-auto px-4 text-center relative z-10">
                <h2 className="text-4xl md:text-5xl font-display font-bold mb-8 text-gray-900 dark:text-white">Ready to ditch the bank fees?</h2>
                <p className="text-xl text-gray-600 dark:text-gray-400 mb-10">Join the thousands of users saving on every remittance with CeloFlow.</p>
                <div className="flex flex-col sm:flex-row justify-center gap-4">
                    <input type="email" placeholder="Enter your email" className="px-6 py-4 rounded-full border border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-celo-green outline-none w-full sm:w-80" />
                    <button 
                        onClick={() => setCurrentView('app')}
                        className="px-8 py-4 bg-black dark:bg-white text-white dark:text-black font-bold rounded-full hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors"
                    >
                        Get Early Access
                    </button>
                </div>
             </div>
        </section>

      </main>

      <footer className="bg-gray-50 dark:bg-gray-900/50 py-12 border-t border-gray-200 dark:border-gray-800 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2">
                <div className="w-6 h-6 bg-gray-900 dark:bg-gray-700 rounded flex items-center justify-center text-white">
                    <Zap className="w-3 h-3 fill-current" />
                </div>
                <span className="font-bold text-gray-900 dark:text-white">CeloFlow</span>
            </div>
            <div className="flex gap-8 text-sm text-gray-500 dark:text-gray-400">
                <a href="#" className="hover:text-gray-900 dark:hover:text-white">Privacy Policy</a>
                <a href="#" className="hover:text-gray-900 dark:hover:text-white">Terms of Service</a>
                <a href="#" className="hover:text-gray-900 dark:hover:text-white">Contact</a>
            </div>
            <p className="text-sm text-gray-400">© 2024 CeloFlow. Built on Celo.</p>
        </div>
      </footer>
    </div>
  );
}

function App() {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <AppContent />
      </QueryClientProvider>
    </WagmiProvider>
  );
}

export default App;