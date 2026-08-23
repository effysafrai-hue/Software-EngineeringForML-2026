import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const REFRESH_TOKEN_KEY = 'se_ml_effy_refresh_token';
const ACCESS_TOKEN_KEY = 'se_ml_effy_access_token';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(() => {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadUser = useCallback(async (token: string) => {
    try {
      const userData = await api.getMe(token);
      setUser(userData);
      setAccessToken(token);
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (storedToken) {
      loadUser(storedToken);
    } else {
      setIsLoading(false);
    }
  }, [loadUser]);

  const login = async (email: string, password: string) => {
    const tokens = await api.login({ email, password });
    setAccessToken(tokens.access_token);
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    await loadUser(tokens.access_token);
  };

  const signup = async (email: string, password: string) => {
    await api.signup({ email, password });
    await login(email, password);
  };

  const logout = () => {
    setUser(null);
    setAccessToken(null);
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setIsLoading(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isAuthenticated: !!user && !!accessToken,
        isLoading,
        login,
        signup,
        logout,
      }}
    >
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
