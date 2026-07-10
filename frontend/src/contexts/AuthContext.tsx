import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "@/api/auth";
import { onAuthEvent, tokenStorage } from "@/api/client";
import type { AuthenticatedUser, LoginPayload } from "@/types/api";
import { toast } from "sonner";

interface AuthContextData {
  user: AuthenticatedUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginPayload, remember?: boolean) => Promise<AuthenticatedUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthContextData | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(() => tokenStorage.getAccess());
  const [isLoading, setLoading] = useState<boolean>(!!tokenStorage.getAccess());

  const loadUser = useCallback(async () => {
    if (!tokenStorage.getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await authApi.me();
      setUser(me);
      setAccessToken(tokenStorage.getAccess());
    } catch {
      setUser(null);
      tokenStorage.clear();
      setAccessToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    return onAuthEvent((event) => {
      if (event === "session-expired") {
        setUser(null);
        setAccessToken(null);
        toast.error("Sua sessão expirou. Faça login novamente.");
        navigate("/login", { replace: true });
      }
    });
  }, [navigate]);

  const login = useCallback(async (data: LoginPayload, remember = false) => {
    tokenStorage.setRemember(remember);
    await authApi.login(data);
    const me = await authApi.me();
    setUser(me);
    setAccessToken(tokenStorage.getAccess());
    return me;
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    setUser(null);
    setAccessToken(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const value = useMemo<AuthContextData>(
    () => ({
      user,
      accessToken,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      refresh: loadUser,
    }),
    [user, accessToken, isLoading, login, logout, loadUser],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
