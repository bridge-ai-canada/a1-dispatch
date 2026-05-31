import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { MagnifyingGlass, ArrowRight, ArrowsClockwise } from "@phosphor-icons/react";

/**
 * Cmd+K / Ctrl+K command palette.
 *
 * - Fuzzy-search over the registered nav items + recent records
 * - Keyboard nav (↑/↓/Enter/Esc)
 * - Lives at the top of <Layout/> so it's available on every authenticated page
 */
export default function CommandPalette({ navItems = [] }) {
    const [open, setOpen] = useState(false);
    const [q, setQ] = useState("");
    const [idx, setIdx] = useState(0);
    const inputRef = useRef(null);
    const navigate = useNavigate();
    const { user } = useAuth();

    // Global hotkey
    useEffect(() => {
        const handler = (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setOpen((o) => !o);
            }
            if (e.key === "Escape") setOpen(false);
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, []);

    useEffect(() => {
        if (open) {
            setQ("");
            setIdx(0);
            setTimeout(() => inputRef.current?.focus(), 30);
        }
    }, [open]);

    // Build action list — pages + quick actions
    const actions = useMemo(() => {
        const quick = [
            { id: "qa-new-job",     label: "Create new work order",  shortcut: "N J", path: "/app/jobs?new=1" },
            { id: "qa-new-est",     label: "Create new estimate",    shortcut: "N E", path: "/app/estimates/new" },
            { id: "qa-new-inv",     label: "Create new invoice",     shortcut: "N I", path: "/app/invoices/new" },
            { id: "qa-new-cust",    label: "Add customer",           shortcut: "N C", path: "/app/customers?new=1" },
            { id: "qa-dispatch",    label: "Open dispatch board",    path: "/app/dispatch" },
            { id: "qa-analytics",   label: "Open analytics",         path: "/app/analytics" },
            { id: "qa-integrations",label: "Open integrations hub",  path: "/app/integrations" },
            { id: "qa-webhooks",    label: "Open webhooks",          path: "/app/integrations/webhooks" },
        ];
        const pages = (navItems || []).map((n) => ({ id: "p-" + n.to, label: n.label, path: n.to }));
        return [...quick, ...pages];
    }, [navItems]);

    const filtered = useMemo(() => {
        if (!q.trim()) return actions.slice(0, 12);
        const needle = q.toLowerCase();
        return actions
            .filter((a) => a.label.toLowerCase().includes(needle))
            .slice(0, 12);
    }, [q, actions]);

    const run = (a) => {
        if (a.path) navigate(a.path);
        setOpen(false);
    };

    if (!open) return null;
    return (
        <div
            className="fixed inset-0 z-[100] bg-slate-950/40 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
            onClick={() => setOpen(false)}
            data-testid="cmdk-overlay"
        >
            <div
                className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-[fadeIn_120ms_ease-out]"
                onClick={(e) => e.stopPropagation()}
                data-testid="cmdk-modal"
            >
                <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100">
                    <MagnifyingGlass size={18} className="text-slate-400" />
                    <input
                        ref={inputRef}
                        value={q}
                        onChange={(e) => { setQ(e.target.value); setIdx(0); }}
                        placeholder="Search pages, jump to…"
                        className="flex-1 outline-none text-sm placeholder-slate-400 bg-transparent"
                        onKeyDown={(e) => {
                            if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(filtered.length - 1, i + 1)); }
                            if (e.key === "ArrowUp")   { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
                            if (e.key === "Enter" && filtered[idx]) { e.preventDefault(); run(filtered[idx]); }
                        }}
                        data-testid="cmdk-input"
                    />
                    <kbd className="text-[10px] font-bold tracking-wider text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">ESC</kbd>
                </div>
                <ul className="max-h-[60vh] overflow-y-auto">
                    {filtered.length === 0 && (
                        <li className="px-4 py-6 text-center text-sm text-slate-400">No matches.</li>
                    )}
                    {filtered.map((a, i) => (
                        <li
                            key={a.id}
                            onMouseEnter={() => setIdx(i)}
                            onClick={() => run(a)}
                            data-testid={`cmdk-item-${a.id}`}
                            className={`flex items-center justify-between gap-3 px-4 py-2.5 cursor-pointer text-sm ${
                                idx === i ? "bg-slate-50" : ""
                            }`}
                        >
                            <span className="flex items-center gap-2 truncate text-slate-800">
                                <ArrowRight size={13} className={idx === i ? "text-[#1D4ED8]" : "text-slate-300"} />
                                {a.label}
                            </span>
                            {a.shortcut && (
                                <kbd className="text-[10px] font-bold tracking-wider text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                                    {a.shortcut}
                                </kbd>
                            )}
                        </li>
                    ))}
                </ul>
                <div className="px-4 py-2 border-t border-slate-100 text-[11px] text-slate-400 flex items-center gap-3">
                    <span><kbd className="font-mono">↑↓</kbd> nav</span>
                    <span><kbd className="font-mono">↵</kbd> open</span>
                    <span className="ml-auto opacity-75">{user?.email}</span>
                </div>
            </div>
        </div>
    );
}
