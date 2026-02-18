import React from 'react';
import { Link } from 'react-router-dom';
import { Bot, ChevronRight, Globe, Lock, Wallet, CheckCircle2, Moon, Sun } from 'lucide-react';
import { WalletConnect } from './WalletConnect';
import { LanguageSwitcher } from './LanguageSwitcher';
import { NAV_LINKS } from '../constants';
import { useI18n } from '../lib/language';

interface LandingPageProps {
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ isDark, setIsDark }) => {
  const { t } = useI18n();

  return (
    <div className="min-h-screen flex flex-col font-sans text-gray-900 dark:text-white bg-white dark:bg-gray-900 transition-colors duration-300 overflow-x-hidden">
      
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-100 dark:border-gray-800 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8">
          <div className="flex justify-between items-center h-14 sm:h-16">
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
              <img 
                src="/logo.png" 
                alt="CeloFlow Logo" 
                className="w-6 h-6 sm:w-8 sm:h-8 rounded-lg"
              />
              <span className="font-display font-bold text-lg sm:text-xl tracking-tight text-gray-900 dark:text-white">CeloFlow</span>
            </div>
            
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center space-x-6 lg:space-x-8">
              {NAV_LINKS.map(link => (
                <a key={link.name} href={link.href} className="text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white transition-colors">
                  {t(link.name)}
                </a>
              ))}
            </div>

            {/* Desktop Actions */}
            <div className="hidden sm:flex items-center gap-2 lg:gap-3">
                <WalletConnect />
                <button 
                    onClick={() => setIsDark(!isDark)}
                    className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
                >
                    {isDark ? <Sun className="w-4 h-4 sm:w-5 sm:h-5" /> : <Moon className="w-4 h-4 sm:w-5 sm:h-5" />}
                </button>
                <Link 
                    to="/app"
                    className="bg-green-600 text-white px-3 lg:px-5 py-2 rounded-full text-xs sm:text-sm font-medium hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors flex items-center gap-1 lg:gap-2"
                >
                    <span className="hidden sm:inline">{t('Launch App')}</span>
                    <span className="sm:hidden">{t('App')}</span>
                    <ChevronRight className="w-3 h-3 sm:w-4 sm:h-4" />
                </Link>
            </div>

            {/* Mobile Actions */}
            <div className="flex sm:hidden items-center gap-2">
                <button 
                    onClick={() => setIsDark(!isDark)}
                    className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
                >
                    {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                </button>
                <Link 
                    to="/app"
                    className="bg-green-600 text-white px-3 py-2 rounded-full text-xs font-medium hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors flex items-center gap-1"
                >
                    {t('App')}
                    <ChevronRight className="w-3 h-3" />
                </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="flex-1 pt-14 sm:pt-16">
        
        {/* Hero Section */}
        <section className="relative bg-white dark:bg-gray-900 overflow-hidden transition-colors duration-300">
            {/* Background Decorations */}
            <div className="absolute top-0 right-0 w-[400px] sm:w-[600px] lg:w-[800px] h-[400px] sm:h-[600px] lg:h-[800px] bg-green-50 dark:bg-green-900/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4 opacity-50 pointer-events-none"></div>
            
            <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8 pt-8 sm:pt-12 lg:pt-24 pb-16 sm:pb-20 lg:pb-32 relative">
                <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
                    
                    {/* Hero Content */}
                    <div className="max-w-xl">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 text-xs font-bold mb-4 sm:mb-6 tracking-wide">
                            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                            {t('SMART AGENT LIVE')}
                        </div>
                        <h1 className="text-3xl sm:text-4xl lg:text-5xl xl:text-7xl font-display font-bold tracking-tight text-gray-900 dark:text-white leading-[1.1] mb-4 sm:mb-6">
                            {t('Send Money Like')} <br/>
                            {t('You Send a')} <span className="text-celo-green">{t('Message')}</span>
                        </h1>
                        <p className="text-base sm:text-lg text-gray-600 dark:text-gray-400 mb-6 sm:mb-8 leading-relaxed max-w-lg">
                            {t('The financial agent that turns your words into instant global transfers on the Celo blockchain. Simple, secure, and fast.')}
                        </p>
                        
                        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                            <Link 
                                to="/app"
                                className="px-6 sm:px-8 py-3 sm:py-4 bg-celo-green text-white font-bold rounded-full hover:bg-green-500 transition-all shadow-xl shadow-green-500/20 active:scale-95 flex items-center justify-center gap-2 text-sm sm:text-base"
                            >
                                <span className="hidden sm:inline">{t('Try CeloFlow Now')}</span>
                                <span className="sm:hidden">{t('Try Now')}</span>
                                <Bot className="w-4 h-4 sm:w-5 sm:h-5" />
                            </Link>
                            <button className="px-6 sm:px-8 py-3 sm:py-4 bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700 font-bold rounded-full hover:bg-gray-50 dark:hover:bg-gray-700 transition-all flex items-center justify-center text-sm sm:text-base">
                                {t('View Activity')}
                            </button>
                        </div>

                        <div className="mt-6 sm:mt-8 flex items-center gap-3 sm:gap-4">
                            <div className="flex -space-x-2 sm:-space-x-3">
                                {[1,2,3].map(i => (
                                    <img key={i} src={`https://picsum.photos/32/32?random=${i}`} className="w-8 h-8 sm:w-10 sm:h-10 rounded-full border-2 border-white dark:border-gray-900" alt="User" />
                                ))}
                            </div>
                            <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 font-medium">{t('Trusted by 10,000+ early users')}</p>
                        </div>
                    </div>

                    {/* Hero Interactive Demo */}
                    <div className="relative lg:min-h-[500px] flex items-center justify-center">
                        <div className="absolute -inset-2 sm:-inset-4 bg-linear-to-r from-green-500 to-blue-500 rounded-3xl sm:rounded-[2.5rem] blur-lg opacity-20 animate-pulse-slow"></div>
                        <div className="relative w-full max-w-sm sm:max-w-md lg:max-w-none">
                          <ChatInterface />
                        </div>
                        
                        {/* Floating Tooltip - Hidden on mobile */}
                        <div className="absolute top-16 -right-4 lg:-right-12 bg-white dark:bg-gray-800 rounded-xl shadow-xl p-3 items-center gap-3 animate-float hidden lg:flex border border-gray-100 dark:border-gray-700">
                             <div className="w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center text-green-600 dark:text-green-400">
                                <CheckCircle2 className="w-6 h-6" />
                             </div>
                             <div>
                                <p className="text-xs text-gray-500 dark:text-gray-400">{t('Just Saved')}</p>
                                <p className="font-bold text-gray-900 dark:text-white">{t('$3.50 vs Bank')}</p>
                             </div>
                        </div>
                    </div>

                </div>
            </div>
        </section>

        {/* Features / Why Celo */}
        <section id="features" className="py-16 sm:py-20 lg:py-24 bg-gray-50 dark:bg-gray-800/50 transition-colors duration-300">
            <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8">
                <div className="text-center max-w-3xl mx-auto mb-12 sm:mb-16">
                    <h2 className="text-2xl sm:text-3xl font-display font-bold text-gray-900 dark:text-white mb-4">{t('Built for the Real World')}</h2>
                    <p className="text-base sm:text-lg text-gray-600 dark:text-gray-400">{t('CeloFlow leverages advanced blockchain infrastructure to make money move as freely as information.')}</p>
                </div>

                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
                    {[
                        {
                            icon: <Globe className="w-6 h-6 text-blue-500" />,
                            title: t('Mento Protocol'),
                            desc: t('Seamlessly swaps stablecoins (cUSD, cEUR, cREAL) with minimal slippage using decentralized stability mechanisms.')
                        },
                        {
                            icon: <Lock className="w-6 h-6 text-green-500" />,
                            title: t('TEE Security'),
                            desc: t('Your keys are managed in a Trusted Execution Environment. You authenticate; the enclave signs. No seed phrases to lose.')
                        },
                        {
                            icon: <Wallet className="w-6 h-6 text-purple-500" />,
                            title: t('Gas Abstraction'),
                            desc: t('Pay transaction fees in the same currency you send. No need to hold CELO just to pay for gas.')
                        }
                    ].map((feature, i) => (
                        <div key={i} className="bg-white dark:bg-gray-800 p-6 sm:p-8 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 hover:shadow-md transition-all">
                            <div className="w-12 h-12 rounded-xl bg-gray-50 dark:bg-gray-700 flex items-center justify-center mb-4 sm:mb-6">
                                {feature.icon}
                            </div>
                            <h3 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white mb-3">{feature.title}</h3>
                            <p className="text-sm sm:text-base text-gray-600 dark:text-gray-400 leading-relaxed">
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
        <section className="py-16 sm:py-20 lg:py-24 bg-white dark:bg-gray-900 relative overflow-hidden transition-colors duration-300">
             <div className="max-w-4xl mx-auto px-3 sm:px-4 text-center relative z-10">
                <h2 className="text-2xl sm:text-3xl lg:text-4xl xl:text-5xl font-display font-bold mb-6 sm:mb-8 text-gray-900 dark:text-white">{t('Ready to ditch the bank fees?')}</h2>
                <p className="text-lg sm:text-xl text-gray-600 dark:text-gray-400 mb-8 sm:mb-10">{t('Join the thousands of users saving on every remittance with CeloFlow.')}</p>
                <div className="flex flex-col sm:flex-row justify-center gap-3 sm:gap-4 max-w-md sm:max-w-none mx-auto">
                    <input type="email" placeholder={t('Enter your email')} className="px-4 sm:px-6 py-3 sm:py-4 rounded-full border border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white focus:border-celo-green outline-none w-full text-sm sm:text-base" />
                    <Link 
                        to="/app"
                        className="px-6 sm:px-8 py-3 sm:py-4 bg-black dark:bg-white text-white dark:text-black font-bold rounded-full hover:bg-gray-800 dark:hover:bg-gray-200 transition-colors text-sm sm:text-base whitespace-nowrap"
                    >
                        {t('Get Early Access')}
                    </Link>
                </div>
             </div>
        </section>

      </main>

      <footer className="bg-gray-50 dark:bg-gray-900/50 py-8 sm:py-12 border-t border-gray-200 dark:border-gray-800 transition-colors duration-300">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 lg:px-8 flex flex-col lg:flex-row justify-between items-center gap-4 lg:gap-6">
            <div className="flex items-center gap-2">
                <img 
                    src="/logo.png" 
                    alt="CeloFlow Logo" 
                    className="w-5 h-5 sm:w-6 sm:h-6 rounded"
                />
                <span className="font-bold text-sm sm:text-base text-gray-900 dark:text-white">CeloFlow</span>
            </div>
            <div className="flex flex-col sm:flex-row gap-4 sm:gap-8 text-xs sm:text-sm text-gray-500 dark:text-gray-400 items-center">
                <a href="#" className="hover:text-gray-900 dark:hover:text-white">{t('Privacy Policy')}</a>
                <a href="#" className="hover:text-gray-900 dark:hover:text-white">{t('Terms of Service')}</a>
                <a href="#" className="hover:text-gray-900 dark:hover:text-white">{t('Contact')}</a>
            </div>
            <p className="text-xs sm:text-sm text-gray-400">{t('©')} {new Date().getFullYear()} {t('CeloFlow. Built on Celo.')}</p>
        </div>
      </footer>
    </div>
  );
};

// Import needed components
import { ChatInterface } from './ChatInterface';
import { SmartRouter } from './SmartRouter';
