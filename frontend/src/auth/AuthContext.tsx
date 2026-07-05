import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as auth from "@/core/auth";
import { disablePush } from "@/core/push";
import { hasSession } from "@/core/tokens";
import type { UserResponse } from "@/core/types";

type Phase = "loading" | "authed" | "anon";

interface AuthState {
  phase: Phase;
  user: UserResponse | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>(hasSession() ? "loading" : "anon");
  const [user, setUser] = useState<UserResponse | null>(null);

  const load = useCallback(async () => {
    try {
      setUser(await auth.me());
      setPhase("authed");
    } catch {
      setPhase("anon");
      setUser(null);
    }
  }, []);

  // Resolve an existing session on first load (validates + fetches the user).
  useEffect(() => {
    if (hasSession()) void load();
  }, [load]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      await auth.login(email, password);
      await load();
    },
    [load],
  );

  // Registration leaves the account unverified — login is gated on a confirmed
  // email, so we stay anon here and the UI prompts the user to check their inbox.
  const signUp = useCallback(
    async (email: string, username: string, password: string) => {
      await auth.register(email, username, password);
    },
    [],
  );

  const signOut = useCallback(async () => {
    // Drop the FCM registration while the tokens are still valid (DELETE
    // /devices needs auth), then revoke the session.
    await disablePush();
    await auth.logout();
    setUser(null);
    setPhase("anon");
  }, []);

  const value = useMemo<AuthState>(
    () => ({ phase, user, signIn, signUp, signOut }),
    [phase, user, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
