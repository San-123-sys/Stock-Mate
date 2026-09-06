import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { auth as authAPI } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem("sm_user");
    return stored ? JSON.parse(stored) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem("sm_token"));
  const [loading, setLoading] = useState(!!localStorage.getItem("sm_token"));

  const isAuthenticated = !!token;

  const _persist = (data, email) => {
    localStorage.setItem("sm_token", data.access_token);
    localStorage.setItem("sm_user", JSON.stringify({ userId: data.user_id, email }));
    setToken(data.access_token);
    setUser({ userId: data.user_id, email });
  };

  // Note: these do NOT touch `loading` — that flag only gates the initial
  // session check in App's route guards. Toggling it here unmounts LoginPage
  // mid-request and wipes its error state. Callers track their own submit state.
  const login = useCallback(async ({ email, password }) => {
    const data = await authAPI.login({ email, password });
    _persist(data, email);
    return data;
  }, []);

  const register = useCallback(async ({ email, password, displayName }) => {
    const data = await authAPI.register({ email, password, display_name: displayName });
    _persist(data, email);
    return data;
  }, []);

  const forgotPassword = useCallback(async (email) => {
    return authAPI.forgotPassword(email);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("sm_token");
    localStorage.removeItem("sm_user");
    localStorage.removeItem("sm_theme");
    setToken(null);
    setUser(null);
    // Reset to dark mode on logout
    const root = window.document.documentElement;
    root.classList.remove("light", "dark");
    root.classList.add("dark");
  }, []);

  // Verify token on mount
  useEffect(() => {
    if (!token) { setLoading(false); return; }
    authAPI.me()
      .then(() => setLoading(false))
      .catch(() => {
        logout();
        setLoading(false);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, loading, login, register, logout, forgotPassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
