"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { API_URL, clearAuthSession, getStoredToken, setStoredToken } from "@/lib/api";
import { homePathForRole, normalizeRole, ROLE_LABELS, type Role } from "@/lib/roles";

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
};

type AuthContextValue = {
  role: Role;
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  logout: () => void;
  homePath: string;
};

const AuthContext = createContext<AuthContextValue>({
  role: "analyst",
  user: null,
  token: null,
  loading: true,
  isAuthenticated: false,
  login: async () => {
    throw new Error("AuthProvider missing");
  },
  logout: () => {},
  homePath: "/workspace",
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const applySession = useCallback((accessToken: string, nextUser: AuthUser) => {
    setStoredToken(accessToken);
    setToken(accessToken);
    setUser(nextUser);
  }, []);

  const logout = useCallback(() => {
    clearAuthSession();
    setToken(null);
    setUser(null);
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }, []);

  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }
    setStoredToken(stored);
    setToken(stored);
    fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${stored}` },
      cache: "no-store",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("unauthorized");
        const data = await res.json();
        setUser({
          id: data.id,
          email: data.email,
          full_name: data.full_name,
          role: normalizeRole(data.role),
        });
      })
      .catch(() => {
        clearAuthSession();
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Login failed");
      }
      const data = await res.json();
      const nextUser: AuthUser = {
        id: data.user.id,
        email: data.user.email,
        full_name: data.user.full_name,
        role: normalizeRole(data.user.role),
      };
      applySession(data.access_token, nextUser);
      return nextUser;
    },
    [applySession],
  );

  const role = user?.role ?? "analyst";
  const value = useMemo(
    () => ({
      role,
      user,
      token,
      loading,
      isAuthenticated: Boolean(token && user),
      login,
      logout,
      homePath: homePathForRole(role),
    }),
    [role, user, token, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

export function useRole() {
  const auth = useAuth();
  return {
    role: auth.role,
    user: auth.user,
    setRole: (_r: Role) => {},
    logout: auth.logout,
    loading: auth.loading,
    isAuthenticated: auth.isAuthenticated,
    homePath: auth.homePath,
  };
}

export { ROLE_LABELS };
