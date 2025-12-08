/**
 * Simplified Auth Context
 *
 * This version bypasses Base44 authentication for local development.
 * In production, this can be extended to use a real auth provider.
 */

import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  // For local development, we'll auto-authenticate
  const [user, setUser] = useState({ id: 'local-dev', name: 'Developer' });
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [isLoadingAuth, setIsLoadingAuth] = useState(false);
  const [isLoadingPublicSettings, setIsLoadingPublicSettings] = useState(false);
  const [authError, setAuthError] = useState(null);
  const [appPublicSettings, setAppPublicSettings] = useState({});

  // Auto-initialize for local dev
  useEffect(() => {
    // Skip auth check for local development
    setIsAuthenticated(true);
    setIsLoadingAuth(false);
    setIsLoadingPublicSettings(false);
  }, []);

  const logout = () => {
    setUser(null);
    setIsAuthenticated(false);
  };

  const navigateToLogin = () => {
    // No-op for local development
    console.log('[AuthContext] navigateToLogin called (no-op in local dev)');
  };

  const checkAppState = async () => {
    // No-op for local development
  };

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      isLoadingAuth,
      isLoadingPublicSettings,
      authError,
      appPublicSettings,
      logout,
      navigateToLogin,
      checkAppState
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
