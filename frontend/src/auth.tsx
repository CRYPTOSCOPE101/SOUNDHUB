import { createContext, useContext, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const raw = localStorage.getItem("soundhub_user");
      return raw ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  });

  const persist = (token: string, u: User) => {
    setToken(token);
    localStorage.setItem("soundhub_user", JSON.stringify(u));
    setUser(u);
  };

  const login = async (username: string, password: string) => {
    const res = await api.login(username, password);
    persist(res.access_token, res.user);
  };

  const register = async (username: string, password: string) => {
    const res = await api.register(username, password);
    persist(res.access_token, res.user);
  };

  const logout = () => {
    setToken(null);
    localStorage.removeItem("soundhub_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function isLoggedIn(): boolean {
  return Boolean(getToken());
}
