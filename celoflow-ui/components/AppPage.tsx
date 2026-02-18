import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Moon, Sun, Users } from 'lucide-react';
import { useAccount } from 'wagmi';
import { ChatInterface } from './ChatInterface';
import { WalletConnect } from './WalletConnect';
import { ContactsManager } from './ContactsManager';
import { LanguageSwitcher } from './LanguageSwitcher';
import { AuthStatus } from './AuthStatus';

interface AppPageProps {
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
}

export const AppPage: React.FC<AppPageProps> = ({ isDark, setIsDark }) => {
  const [showContacts, setShowContacts] = useState(false);
  const { address: walletAddress } = useAccount();

  return (
    <div className="min-h-screen flex flex-col font-sans bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
      <nav className="sticky top-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 transition-colors duration-300">
          <div className="flex items-center gap-2 cursor-pointer group">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="p-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 group-hover:bg-gray-200 dark:group-hover:bg-gray-700 transition-colors">
                 <ArrowLeft className="w-5 h-5" />
              </div>
              <span className="font-display font-bold text-xl tracking-tight text-gray-900 dark:text-white group-hover:opacity-80 transition-opacity">CeloFlow</span>
            </Link>
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
               <AuthStatus walletAddress={walletAddress} />
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
};
