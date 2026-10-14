import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';
import {
  clearAccessToken, getAccessToken, getCurrentUser, login as requestLogin,
  storeAccessToken, type AuthUser,
} from '../services/auth';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  sessionError: string | null;
  signIn: (email: string, password: string, role: AuthUser['role']) => Promise<AuthUser>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      setLoading(false);
      return;
    }

    let active = true;
    getCurrentUser()
      .then((account) => {
        if (active) setUser(account);
      })
      .catch((cause: unknown) => {
        const status = (cause as { response?: { status?: number } })?.response?.status;
        if (status === 401 || status === 403) clearAccessToken();
        if (active) {
          setUser(null);
          if (status !== 401 && status !== 403) {
            setSessionError('Unable to verify your session. Check the service connection, then sign in again.');
          }
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, []);

  const signIn = useCallback(async (email: string, password: string, role: AuthUser['role']) => {
    const result = await requestLogin(email, password);
    if (result.user.role !== role) {
      throw new Error(`This account uses the ${result.user.role} workspace. Select that role and sign in again.`);
    }
    storeAccessToken(result.access_token);
    setSessionError(null);
    setUser(result.user);
    return result.user;
  }, []);

  const signOut = useCallback(() => {
    clearAccessToken();
    setSessionError(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, sessionError, signIn, signOut }),
    [user, loading, sessionError, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider.');
  return context;
}
