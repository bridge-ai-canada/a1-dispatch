import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [company, setCompany] = useState(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            const { data } = await api.get("/auth/me");
            setUser(data.user);
            setCompany(data.company);
        } catch {
            setUser(false);
            setCompany(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        // CRITICAL: If returning from OAuth callback, skip the /me check.
        // AuthCallback will exchange the session_id and establish the session first.
        if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
            setLoading(false);
            return;
        }
        refresh();
    }, [refresh]);

    // Apply tenant branding as CSS vars + document title whenever company changes.
    useEffect(() => {
        if (!company) return;
        const b = company.branding || {};
        const root = document.documentElement;
        if (b.primary_color) root.style.setProperty("--brand-primary", b.primary_color);
        if (b.accent_color) root.style.setProperty("--brand-accent", b.accent_color);
        if (b.secondary_color) root.style.setProperty("--brand-secondary", b.secondary_color);
        const appName = b.app_name || company.name;
        if (appName) document.title = appName;
    }, [company]);

    const login = async (email, password, mfa_code) => {
        const { data } = await api.post("/auth/login", { email, password, mfa_code });
        if (data.token) try { localStorage.setItem("a1.token", data.token); } catch (_) {}
        setUser(data.user);
        await refresh();
        return data.user;
    };

    const register = async (payload) => {
        const { data } = await api.post("/auth/register", payload);
        if (data.token) try { localStorage.setItem("a1.token", data.token); } catch (_) {}
        setUser(data.user);
        await refresh();
        return data.user;
    };

    const logout = async () => {
        try { await api.post("/auth/logout"); } catch {}
        try { localStorage.removeItem("a1.token"); } catch (_) {}
        setUser(false);
        setCompany(null);
    };

    return (
        <AuthContext.Provider value={{ user, company, loading, login, register, logout, refresh }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
