import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import * as SecureStore from "expo-secure-store";
import { api } from "./api";

const TOKEN_KEY = "a1.token";

export async function getToken() {
    try { return await SecureStore.getItemAsync(TOKEN_KEY); } catch { return null; }
}
export async function setToken(t: string | null) {
    if (!t) return SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => {});
    return SecureStore.setItemAsync(TOKEN_KEY, t);
}

type User = { id: string; email: string; name: string; role: string; company_id?: string | null };
type AuthCtx = {
    user: User | null;
    loading: boolean;
    signIn: (email: string, password: string) => Promise<void>;
    signOut: () => Promise<void>;
    refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);

    const refresh = async () => {
        const token = await getToken();
        if (!token) { setUser(null); setLoading(false); return; }
        try {
            const { data } = await api.get("/auth/me");
            setUser(data.user);
        } catch {
            await setToken(null);
            setUser(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { refresh(); }, []);

    const signIn = async (email: string, password: string) => {
        const { data } = await api.post("/auth/login", { email, password });
        await setToken(data.token);
        setUser(data.user);
    };

    const signOut = async () => {
        await api.post("/auth/logout").catch(() => {});
        await setToken(null);
        setUser(null);
    };

    return <Ctx.Provider value={{ user, loading, signIn, signOut, refresh }}>{children}</Ctx.Provider>;
}

export function useAuth() {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error("useAuth must be inside <AuthProvider>");
    return ctx;
}
