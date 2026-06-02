import React, { createContext, useContext, useState, useEffect } from 'react';
import { signIn as cognitoSignIn, signOut as cognitoSignOut } from './cognito';
import { getIdToken, getSessionData } from './storage';

interface AuthContextType {
  user: string | null;
  role: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<any>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const bootstrapAsync = async () => {
      try {
        const token = await getIdToken();
        const sessionDataStr = await getSessionData();
        
        if (token && sessionDataStr) {
          const sessionData = JSON.parse(sessionDataStr);
          setUser(sessionData.email);
          setRole(sessionData.role);
        }
      } catch (e) {
        console.warn('Failed to restore identity token', e);
      } finally {
        setIsLoading(false);
      }
    };

    bootstrapAsync();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const session = await cognitoSignIn(email, password);
      // If the sign in resolved a challenge, handle accordingly
      if ((session as any).challenge) {
        setIsLoading(false);
        return session;
      }
      
      const sessionDataStr = await getSessionData();
      if (sessionDataStr) {
        const sessionData = JSON.parse(sessionDataStr);
        setUser(sessionData.email);
        setRole(sessionData.role);
      }
      setIsLoading(false);
      return session;
    } catch (error) {
      setIsLoading(false);
      throw error;
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await cognitoSignOut();
      setUser(null);
      setRole(null);
    } catch (error) {
      console.warn('Sign out encountered error', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
