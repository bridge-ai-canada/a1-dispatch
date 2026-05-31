import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

const Ctx = createContext({ open: false, toggle: () => {}, close: () => {} });

export function CommandPaletteProvider({ children }) {
    const [open, setOpen] = useState(false);
    const openRef = useRef(false);
    openRef.current = open;

    const toggle = useCallback(() => setOpen((o) => !o), []);
    const close = useCallback(() => setOpen(false), []);

    // Bind listener once — read latest `open` via ref to avoid rebinds.
    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                const el = document.activeElement;
                const isEditable = el && (
                    el.tagName === "INPUT" || el.tagName === "TEXTAREA" ||
                    el.isContentEditable
                );
                if (isEditable && !openRef.current) return;
                e.preventDefault();
                setOpen((o) => !o);
            }
            if (e.key === "Escape") setOpen(false);
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, []);

    return (
        <Ctx.Provider value={{ open, toggle, close }}>
            {children}
        </Ctx.Provider>
    );
}

export const useCommandPalette = () => useContext(Ctx);
