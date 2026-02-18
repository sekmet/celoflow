import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { LandingPage } from './LandingPage';
import { AppPage } from './AppPage';
import { ScrollToTop } from './ScrollToTop';

export const AppRouter: React.FC = () => {
  const [isDark, setIsDark] = useState(() => {
    // Initialize theme from localStorage or system preference
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem('celoflow-theme');
      if (savedTheme) {
        return savedTheme === 'dark';
      }
      // Fallback to system preference
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  useEffect(() => {
    // Update DOM and localStorage when theme changes
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('celoflow-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('celoflow-theme', 'light');
    }
  }, [isDark]);

  return (
    <Router>
      <ScrollToTop />
      <Routes>
        <Route 
          path="/" 
          element={<LandingPage isDark={isDark} setIsDark={setIsDark} />} 
        />
        <Route 
          path="/app" 
          element={<AppPage isDark={isDark} setIsDark={setIsDark} />} 
        />
      </Routes>
    </Router>
  );
};
