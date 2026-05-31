import { createContext, useCallback, useContext, useEffect, useState } from "react";

const Ctx = createContext({ open: false, toggle: () => {}, close: () => {} });

export function CommandPaletteProvider({ children }) {
    const [open, setOpen] = useState(false);

    const toggle = useCallback(() => setOpen((o) => !o), []);
    const close = useCallback(() => setOpen(false), []);
    const openIt = useCallback(() => setOpen(true), []);

    // Global hotkey lives at provider level so any descendant component can
    // react to it without re-binding window listeners.
    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                const el = document.activeElement;
                const isEditable = el && (
                    el.tagName === "INPUT" || el.tagName === "TEXTAREA" ||
                    el.isContentEditable
                );
                if (isEditable && !open) return;
                e.preventDefault();
                setOpen((o) => !o);
            }
            if (e.key === "Escape") setOpen(false);
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [open]);

    return (
        <Ctx.Provider value={{ open, toggle, close, open_: openIt }}>
            {children}
        </Ctx.Provider>
    );
}

export const useCommandPalette = () => useContext(Ctx);
