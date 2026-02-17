import React, { useState, useEffect } from 'react';
import { Globe, ChevronDown, Check } from 'lucide-react';

interface Language {
  code: string;
  name: string;
  nativeName: string;
  flag: string;
}

const LANGUAGES: Language[] = [
  { code: 'en', name: 'English', nativeName: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Spanish', nativeName: 'Español', flag: '🇪🇸' },
  { code: 'pt', name: 'Portuguese', nativeName: 'Português', flag: '🇧🇷' },
  { code: 'fr', name: 'French', nativeName: 'Français', flag: '🇫🇷' },
  { code: 'de', name: 'German', nativeName: 'Deutsch', flag: '🇩🇪' },
  { code: 'it', name: 'Italian', nativeName: 'Italiano', flag: '🇮🇹' },
];

const STORAGE_KEY = 'celoflow_language';

function getStoredLanguage(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || 'en';
  } catch {
    return 'en';
  }
}

function storeLanguage(code: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // ignore
  }
}

interface LanguageSwitcherProps {
  onLanguageChange?: (code: string) => void;
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({ onLanguageChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState(getStoredLanguage);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-lang-switcher]')) {
        setIsOpen(false);
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const handleSelect = (code: string) => {
    setSelected(code);
    storeLanguage(code);
    setIsOpen(false);
    onLanguageChange?.(code);
  };

  const current = LANGUAGES.find((l) => l.code === selected) || LANGUAGES[0];

  return (
    <div className="relative" data-lang-switcher>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-gray-600 dark:text-gray-300"
        title={`Language: ${current.name}`}
      >
        <Globe className="w-5 h-5" />
        <span className="text-xs font-medium hidden sm:inline">{current.flag}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-52 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden z-50 animate-fade-in-up">
          <div className="px-4 py-2.5 border-b border-gray-100 dark:border-gray-700">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Language
            </span>
          </div>
          <div className="py-1">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleSelect(lang.code)}
                className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  selected === lang.code
                    ? 'bg-green-50 dark:bg-green-900/20 text-celo-green font-medium'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                }`}
              >
                <span className="text-base">{lang.flag}</span>
                <div className="flex-1 text-left">
                  <div className="font-medium">{lang.nativeName}</div>
                  <div className="text-xs text-gray-400">{lang.name}</div>
                </div>
                {selected === lang.code && (
                  <Check className="w-4 h-4 text-celo-green shrink-0" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
