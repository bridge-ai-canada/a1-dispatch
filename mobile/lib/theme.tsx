import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";

export type Palette = {
    ink: string;
    paper: string;
    soft: string;
    muted: string;
    line: string;
    primary: string;
    accent: string;
    ok: string;
    warn: string;
    surface2: string;
};

export const lightPalette: Palette = {
    ink: "#0F172A",
    paper: "#FFFFFF",
    soft: "#F8FAFC",
    muted: "#64748B",
    line: "#E2E8F0",
    primary: "#1D4ED8",
    accent: "#DC2626",
    ok: "#16A34A",
    warn: "#D97706",
    surface2: "#F1F5F9",
};

export const darkPalette: Palette = {
    ink: "#F8FAFC",
    paper: "#1E293B",
    soft: "#0B1220",
    muted: "#94A3B8",
    line: "#334155",
    primary: "#60A5FA",
    accent: "#F87171",
    ok: "#4ADE80",
    warn: "#FBBF24",
    surface2: "#1F2937",
};

// Backward-compat export so existing files keep working until migrated
export const colors = lightPalette;

type Mode = "light" | "dark" | "system";

type Ctx = {
    mode: Mode;
    isDark: boolean;
    palette: Palette;
    setMode: (m: Mode) => void;
};

const ThemeCtx = createContext<Ctx | null>(null);
const KEY = "a1.theme.v1";

export function ThemeProvider({ children, systemDark = false }: { children: ReactNode; systemDark?: boolean }) {
    const [mode, setMode] = useState<Mode>("light");

    useEffect(() => {
        AsyncStorage.getItem(KEY).then((v) => {
            if (v === "light" || v === "dark" || v === "system") setMode(v);
        });
    }, []);

    const update = (m: Mode) => {
        setMode(m);
        AsyncStorage.setItem(KEY, m).catch(() => {});
    };

    const isDark = mode === "dark" || (mode === "system" && systemDark);
    const palette = isDark ? darkPalette : lightPalette;
    return <ThemeCtx.Provider value={{ mode, isDark, palette, setMode: update }}>{children}</ThemeCtx.Provider>;
}

export function useTheme() {
    const ctx = useContext(ThemeCtx);
    if (!ctx) {
        // fallback to light palette so non-themed consumers don't crash
        return { mode: "light" as Mode, isDark: false, palette: lightPalette, setMode: () => {} };
    }
    return ctx;
}
