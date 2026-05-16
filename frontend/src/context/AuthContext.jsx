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
        refresh();
    }, [refresh]);

    const login = async (email, password, mfa_code) => {
        const { data } = await api.post("/auth/login", { email, password, mfa_code });
        setUser(data.user);
        await refresh();
        return data.user;
    };

    const register = async (payload) => {
        const { data } = await api.post("/auth/register", payload);
        setUser(data.user);
        await refresh();
        return data.user;
    };

    const logout = async () => {
        try { await api.post("/auth/logout"); } catch {}
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
