import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Plus, Wrench, AddressBook, FileText, Receipt, Bank,
} from "@phosphor-icons/react";
import { useAuth } from "../context/AuthContext";

/**
 * Floating action button — global "create" shortcut.
 *
 * Tap → fan-out menu with role-aware quick-create actions.
 * Replaces 3-5 clicks ("nav → page → New button → form") with one tap.
 */
const ACTIONS = [
    { key: "job",        label: "Work order", icon: Wrench,      path: "/app/jobs?new=1",       roles: ["owner","dispatcher","office_manager","csr","sales_rep"] },
    { key: "customer",   label: "Customer",   icon: AddressBook, path: "/app/customers?new=1",  roles: ["owner","dispatcher","office_manager","csr","sales_rep","technician"] },
    { key: "estimate",   label: "Estimate",   icon: FileText,    path: "/app/estimates/new",    roles: ["owner","dispatcher","office_manager","csr","sales_rep","technician"] },
    { key: "invoice",    label: "Invoice",    icon: Receipt,     path: "/app/invoices/new",     roles: ["owner","dispatcher","office_manager","accountant"] },
    { key: "finance",    label: "Finance job",icon: Bank,        path: "/app/financing",        roles: ["owner","dispatcher","office_manager","sales_rep","csr","accountant","technician"] },
];

export default function QuickCreateFAB() {
    const [open, setOpen] = useState(false);
    const navigate = useNavigate();
    const { user } = useAuth();
    if (!user) return null;
    const items = ACTIONS.filter((a) => a.roles.includes(user.role));
    if (items.length === 0) return null;

    return (
        <div className="fixed bottom-5 right-5 z-40 sm:bottom-6 sm:right-6" data-testid="fab">
            {/* Backdrop when expanded */}
            {open && (
                <div className="fixed inset-0 -z-10" onClick={() => setOpen(false)} />
            )}
            {/* Fan-out actions */}
            <div className={`flex flex-col-reverse items-end gap-2 mb-2 transition-all ${
                open ? "opacity-100 translate-y-0" : "opacity-0 pointer-events-none translate-y-2"
            }`}>
                {items.map((a, i) => (
                    <button
                        key={a.key}
                        onClick={() => { setOpen(false); navigate(a.path); }}
                        data-testid={`fab-${a.key}`}
                        style={{ transitionDelay: open ? `${i * 30}ms` : "0ms" }}
                        className="group flex items-center gap-2 bg-white border border-slate-200 shadow-lg hover:shadow-xl rounded-full pl-3 pr-4 py-2 text-sm font-bold transition-all hover:scale-[1.03]"
                    >
                        <a.icon size={16} className="text-[#1D4ED8]" weight="duotone" />
                        {a.label}
                    </button>
                ))}
            </div>
            {/* Main FAB */}
            <button
                onClick={() => setOpen((o) => !o)}
                data-testid="fab-toggle"
                aria-label="Quick create"
                className={`w-14 h-14 rounded-full bg-[#1D4ED8] text-white shadow-2xl flex items-center justify-center transition-all hover:scale-105 active:scale-95 ${
                    open ? "rotate-45" : ""
                }`}
            >
                <Plus size={26} weight="bold" />
            </button>
        </div>
    );
}
