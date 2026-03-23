import { createContext, useContext, useState, useEffect, ReactNode, createElement } from 'react';
import * as SecureStore from 'expo-secure-store';

const JWT_KEY = 'gt_jwt_token';
const USER_KEY = 'gt_user';

export interface User {
  email: string;
  username: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isTrusted: boolean;
  signIn: (token: string, user: User) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const storedToken = await SecureStore.getItemAsync(JWT_KEY);
        const storedUser = await SecureStore.getItemAsync(USER_KEY);
        if (storedToken && storedUser) {
          setToken(storedToken);
          setUser(JSON.parse(storedUser));
        }
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  async function signIn(newToken: string, newUser: User) {
    await SecureStore.setItemAsync(JWT_KEY, newToken);
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  }

  async function signOut() {
    await SecureStore.deleteItemAsync(JWT_KEY);
    await SecureStore.deleteItemAsync(USER_KEY);
    setToken(null);
    setUser(null);
  }

  const isTrusted = user?.role === 'trusted' || user?.role === 'admin';

  return createElement(AuthContext.Provider, { value: { user, token, isLoading, isTrusted, signIn, signOut } }, children);
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
