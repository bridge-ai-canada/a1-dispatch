import { NavLink, Outlet, useNavigate, useLocation, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Brand from "./Brand";
import {
    SquaresFour, Wrench, CalendarBlank, UsersThree,
    AddressBook, GearSix, SignOut, List, X, DeviceMobile,
    ShieldCheck, ClockCounterClockwise, Buildings, EnvelopeSimple,
    ArrowsClockwise, ChartLine, Broadcast, FileText, Receipt, Stack, Sparkle,
} from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import OfflineIndicator from "./OfflineIndicator";

const baseNav = [
    { to: "/app/dashboard", label: "Dashboard", icon: SquaresFour, roles: ["owner","dispatcher","office_manager","csr","sales_rep","accountant","technician"] },
    { to: "/app/jobs", label: "Work Orders", icon: Wrench, roles: ["owner","dispatcher","office_manager","csr","sales_rep","accountant"] },
    { to: "/app/dispatch", label: "Dispatch", icon: Broadcast, roles: ["owner","dispatcher","office_manager"] },
    { to: "/app/schedule", label: "Schedule", icon: CalendarBlank, roles: ["owner","dispatcher","office_manager"] },
    { to: "/app/team", label: "Team", icon: UsersThree, roles: ["owner","dispatcher","office_manager"] },
    { to: "/app/customers", label: "Customers", icon: AddressBook, roles: ["owner","dispatcher","office_manager","csr","sales_rep"] },
    { to: "/app/estimates", label: "Estimates", icon: FileText, roles: ["owner","dispatcher","office_manager","csr","sales_rep","accountant"] },
    { to: "/app/invoices", label: "Invoices", icon: Receipt, roles: ["owner","dispatcher","office_manager","accountant"] },
    { to: "/app/templates", label: "Templates", icon: Stack, roles: ["owner","office_manager"] },
    { to: "/app/ai", label: "AI Assistant", icon: Sparkle, roles: ["owner","dispatcher","office_manager"] },
    { to: "/app/my-jobs", label: "My Jobs", icon: DeviceMobile, roles: ["owner","dispatcher","technician"] },
    { to: "/app/recurring", label: "Recurring", icon: ArrowsClockwise, roles: ["owner","dispatcher","office_manager"] },
    { to: "/app/reports", label: "Reports", icon: ChartLine, roles: ["owner","accountant","super_admin"] },
    { to: "/app/admin/users", label: "Users", icon: ShieldCheck, roles: ["owner","super_admin"] },
    { to: "/app/admin/activity", label: "Activity", icon: ClockCounterClockwise, roles: ["owner","office_manager","accountant","super_admin"] },
    { to: "/app/settings", label: "Settings", icon: GearSix, roles: ["owner","super_admin"] },
];

export default function Layout() {
    const { user, company, logout } = useAuth();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);

    if (!user) return null;
    const nav = baseNav.filter((n) => n.roles.includes(user.role));

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    return (
        <div className="min-h-screen bg-white text-slate-900">
            <OfflineIndicator />
            {/* Top bar */}
            <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
                <div className="flex h-14 items-center justify-between px-4 md:px-6">
                    <div className="flex items-center gap-3">
                        <button
                            className="lg:hidden -ml-1 p-2"
                            onClick={() => setOpen(!open)}
                            data-testid="menu-toggle-button"
                            aria-label="Toggle menu"
                        >
                            {open ? <X size={22} /> : <List size={22} />}
                        </button>
                        <Brand />
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="hidden sm:block text-right leading-tight">
                            <div className="text-sm font-semibold" data-testid="user-name">{user.name}</div>
                            <div className="overline">{company?.name || user.role}</div>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="flex h-9 w-9 items-center justify-center border border-slate-300 hover:bg-slate-50"
                            data-testid="logout-button"
                            aria-label="Sign out"
                        >
                            <SignOut size={18} />
                        </button>
                    </div>
                </div>
            </header>

            <div className="flex">
                {/* Sidebar */}
                <aside
                    className={`fixed lg:sticky lg:top-14 top-14 z-20 h-[calc(100vh-3.5rem)] w-64 shrink-0 border-r border-slate-200 bg-white transform transition-transform lg:translate-x-0 ${
                        open ? "translate-x-0" : "-translate-x-full"
                    }`}
                    data-testid="sidebar"
                >
                    <nav className="flex flex-col p-3 gap-1">
                        {nav.map((item) => (
                            <NavLink
                                key={item.to}
                                to={item.to}
                                onClick={() => setOpen(false)}
                                data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g,"-")}-link`}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-3 py-2 text-sm font-medium border-l-2 transition-colors ${
                                        isActive
                                            ? "border-[#DC2626] bg-slate-50 text-slate-900"
                                            : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                                    }`
                                }
                            >
                                <item.icon size={18} weight="duotone" />
                                {item.label}
                            </NavLink>
                        ))}
                    </nav>
                    <div className="absolute bottom-0 left-0 right-0 border-t border-slate-200 p-4">
                        <div className="overline mb-1">Plan</div>
                        <div className="text-sm font-semibold">Pro · Trial</div>
                        <div className="text-xs text-slate-500 mt-0.5">14 days remaining</div>
                    </div>
                </aside>

                {/* Backdrop for mobile */}
                {open && (
                    <div
                        className="fixed inset-0 z-10 bg-black/30 lg:hidden"
                        onClick={() => setOpen(false)}
                    />
                )}

                <main className="flex-1 min-w-0 p-4 md:p-8">
                    <VerifyBanner user={user} />
                    <Outlet />
                </main>
            </div>
        </div>
    );
}

export function Protected({ children, roles }) {
    const { user, loading } = useAuth();
    const location = useLocation();
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="h-10 w-10 border-2 border-slate-200 border-t-[#1D4ED8] rounded-full animate-spin" />
            </div>
        );
    }
    if (!user) {
        window.location.href = "/login";
        return null;
    }
    if (roles && !roles.includes(user.role)) {
        return (
            <div className="p-8 text-center">
                <h2 className="font-display text-2xl">Access restricted</h2>
                <p className="mt-2 text-slate-600">You don't have permission to view this page.</p>
            </div>
        );
    }
    return children;
}


function VerifyBanner({ user }) {
    const [dismissed, setDismissed] = useState(false);
    const [resending, setResending] = useState(false);
    if (!user || user.email_verified || dismissed) return null;
    const resend = async () => {
        setResending(true);
        try {
            const { data } = await api.post("/auth/verify/resend");
            toast.success(data.email_sent ? "Verification email sent" : "Verification link refreshed (email not sent — Resend free tier)");
        } catch {
            toast.error("Could not resend");
        } finally { setResending(false); }
    };
    return (
        <div className="mb-6 p-3 border-l-2 border-amber-500 bg-amber-50 flex items-center justify-between gap-3" data-testid="verify-banner">
            <div className="flex items-center gap-2 text-sm text-amber-900">
                <EnvelopeSimple size={18} weight="duotone" />
                <span>Verify <strong>{user.email}</strong> to receive invoices and booking confirmations.</span>
            </div>
            <div className="flex items-center gap-2">
                <button onClick={resend} disabled={resending} data-testid="verify-resend-button"
                    className="text-xs font-semibold px-3 py-1.5 bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-60">
                    {resending ? "Sending..." : "Resend"}
                </button>
                <button onClick={() => setDismissed(true)} aria-label="Dismiss" className="p-1"><X size={16} /></button>
            </div>
        </div>
    );
}
