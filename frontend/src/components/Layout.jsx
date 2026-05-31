import { NavLink, Outlet, useNavigate, useLocation, Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Brand from "./Brand";
import {
    SquaresFour, Wrench, CalendarBlank, UsersThree,
    AddressBook, GearSix, SignOut, List, X, DeviceMobile,
    ShieldCheck, ClockCounterClockwise, Buildings, EnvelopeSimple,
    ArrowsClockwise, ChartLine, Broadcast, FileText, Receipt, Stack, Sparkle,
    Kanban, PaintBrush, ChatText, CreditCard, Key, Globe, Bank, Plugs, Lightning,
    MagnifyingGlass, CaretDown,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import OfflineIndicator from "./OfflineIndicator";
import CommandPalette from "./CommandPalette";
import QuickCreateFAB from "./QuickCreateFAB";
import { useCommandPalette } from "../context/CommandPaletteContext";

// Nav grouped by section — reduces cognitive load (was 28 flat items)
const NAV_GROUPS = [
    {
        section: "Operations",
        items: [
            { to: "/app/dashboard", label: "Dashboard", icon: SquaresFour, roles: ["owner","dispatcher","office_manager","csr","sales_rep","accountant","technician"] },
            { to: "/app/jobs",      label: "Work Orders", icon: Wrench, roles: ["owner","dispatcher","office_manager","csr","sales_rep","accountant"] },
            { to: "/app/pipeline",  label: "Pipeline", icon: Kanban, roles: ["owner","dispatcher","office_manager","sales_rep"] },
            { to: "/app/dispatch",  label: "Dispatch", icon: Broadcast, roles: ["owner","dispatcher","office_manager"] },
            { to: "/app/schedule",  label: "Schedule", icon: CalendarBlank, roles: ["owner","dispatcher","office_manager"] },
            { to: "/app/team",      label: "Team", icon: UsersThree, roles: ["owner","dispatcher","office_manager"] },
            { to: "/app/my-jobs",   label: "My Jobs", icon: DeviceMobile, roles: ["owner","dispatcher","technician"] },
            { to: "/app/recurring", label: "Recurring", icon: ArrowsClockwise, roles: ["owner","dispatcher","office_manager"] },
        ],
    },
    {
        section: "Sales",
        items: [
            { to: "/app/customers",  label: "Customers", icon: AddressBook, roles: ["owner","dispatcher","office_manager","csr","sales_rep"] },
            { to: "/app/estimates",  label: "Estimates", icon: FileText, roles: ["owner","dispatcher","office_manager","csr","sales_rep","accountant"] },
            { to: "/app/templates",  label: "Templates", icon: Stack, roles: ["owner","office_manager"] },
            { to: "/app/ai",         label: "AI Assistant", icon: Sparkle, roles: ["owner","dispatcher","office_manager"] },
        ],
    },
    {
        section: "Money",
        items: [
            { to: "/app/invoices",            label: "Invoices", icon: Receipt, roles: ["owner","dispatcher","office_manager","accountant"] },
            { to: "/app/financing",           label: "Financing", icon: Bank, roles: ["owner","dispatcher","office_manager","sales_rep","csr","accountant"] },
            { to: "/app/financing/programs",  label: "Finance programs", icon: Bank, roles: ["owner","super_admin"] },
            { to: "/app/admin/financing",     label: "Finance admin", icon: Bank, roles: ["super_admin"] },
        ],
    },
    {
        section: "Insights",
        items: [
            { to: "/app/reports",   label: "Reports", icon: ChartLine, roles: ["owner","accountant","super_admin"] },
            { to: "/app/analytics", label: "Analytics", icon: ChartLine, roles: ["owner","office_manager","accountant","super_admin"] },
        ],
    },
    {
        section: "Platform",
        items: [
            { to: "/app/integrations",           label: "Integrations", icon: Plugs, roles: ["owner","office_manager","super_admin"] },
            { to: "/app/integrations/webhooks",  label: "Webhooks", icon: Lightning, roles: ["owner","office_manager","super_admin"] },
            { to: "/app/admin/users",            label: "Users", icon: ShieldCheck, roles: ["owner","super_admin"] },
            { to: "/app/admin/activity",         label: "Activity", icon: ClockCounterClockwise, roles: ["owner","office_manager","accountant","super_admin"] },
            { to: "/app/super/tenants",          label: "Tenants", icon: Globe, roles: ["super_admin"] },
        ],
    },
    {
        section: "Settings",
        items: [
            { to: "/app/settings/branding",      label: "Branding", icon: PaintBrush, roles: ["owner","super_admin"] },
            { to: "/app/settings/branches",      label: "Branches", icon: Buildings, roles: ["owner","office_manager","super_admin"] },
            { to: "/app/settings/templates",     label: "Messages", icon: ChatText, roles: ["owner","office_manager","super_admin"] },
            { to: "/app/settings/subscription",  label: "Subscription", icon: CreditCard, roles: ["owner","super_admin"] },
            { to: "/app/settings/api-keys",      label: "API keys", icon: Key, roles: ["owner","super_admin"] },
            { to: "/app/settings",               label: "Settings", icon: GearSix, roles: ["owner","super_admin"] },
        ],
    },
];

// Flat list (for Cmd+K)
const flatNav = NAV_GROUPS.flatMap((g) => g.items);

export default function Layout() {
    const { user, company, logout } = useAuth();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const cmdk = useCommandPalette();

    // Memoize before any early return — hooks must run in same order every render.
    const role = user?.role || "";
    const visibleGroups = useMemo(
        () => NAV_GROUPS
            .map((g) => ({ ...g, items: g.items.filter((i) => i.roles.includes(role)) }))
            .filter((g) => g.items.length > 0),
        [role],
    );
    const navForCmdk = useMemo(
        () => flatNav.filter((n) => n.roles.includes(role)),
        [role],
    );

    if (!user) return null;

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <OfflineIndicator />
            <CommandPalette navItems={navForCmdk} />
            {/* Top bar */}
            <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/85 backdrop-blur supports-[backdrop-filter]:bg-white/70">
                <div className="flex h-14 items-center justify-between px-3 md:px-6">
                    <div className="flex items-center gap-3 min-w-0">
                        <button
                            className="lg:hidden -ml-1 p-2 rounded hover:bg-slate-100"
                            onClick={() => setOpen(!open)}
                            data-testid="menu-toggle-button"
                            aria-label="Toggle menu"
                        >
                            {open ? <X size={22} /> : <List size={22} />}
                        </button>
                        <Brand />
                    </div>
                    {/* Cmd+K hint */}
                    <button
                        onClick={cmdk.toggle}
                        data-testid="cmdk-trigger"
                        className="hidden md:flex items-center gap-2 px-3 h-9 rounded-lg border border-slate-200 bg-white text-xs text-slate-500 hover:bg-slate-50 transition-colors min-w-[180px] lg:min-w-[260px]"
                    >
                        <MagnifyingGlass size={14} />
                        <span className="flex-1 text-left truncate">Search or jump to…</span>
                        <kbd className="font-mono text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">⌘K</kbd>
                    </button>
                    <div className="flex items-center gap-3">
                        <div className="hidden sm:block text-right leading-tight">
                            <div className="text-sm font-semibold truncate max-w-[200px]" data-testid="user-name">{user.name}</div>
                            <div className="overline">{company?.name || user.role}</div>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors"
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
                    className={`fixed lg:sticky lg:top-14 top-14 z-20 h-[calc(100vh-3.5rem)] w-64 shrink-0 border-r border-slate-200 bg-white transform transition-transform duration-200 ease-out lg:translate-x-0 ${
                        open ? "translate-x-0" : "-translate-x-full"
                    }`}
                    data-testid="sidebar"
                >
                    <nav className="flex flex-col p-3 gap-4 overflow-y-auto h-[calc(100%-90px)]">
                        {visibleGroups.map((group) => (
                            <NavGroup key={group.section} group={group} onItemClick={() => setOpen(false)} />
                        ))}
                    </nav>
                    <div className="absolute bottom-0 left-0 right-0 border-t border-slate-200 p-4 bg-white">
                        <div className="overline mb-1">Plan</div>
                        <div className="text-sm font-semibold">{company?.subscription?.plan ? company.subscription.plan : "Pro · Trial"}</div>
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

                <main className="flex-1 min-w-0 p-4 md:p-8 lg:pl-8 max-w-full">
                    <VerifyBanner user={user} />
                    <Outlet />
                </main>
            </div>

            {/* Global quick-create FAB */}
            <QuickCreateFAB />
        </div>
    );
}

function NavGroup({ group, onItemClick }) {
    // Cache open/closed per group in localStorage
    const lsKey = `nav.collapsed.${group.section}`;
    const [collapsed, setCollapsed] = useState(() => {
        try { return localStorage.getItem(lsKey) === "1"; } catch { return false; }
    });
    useEffect(() => {
        try { localStorage.setItem(lsKey, collapsed ? "1" : "0"); } catch (_) { /* no-op */ }
    }, [collapsed, lsKey]);

    return (
        <div>
            <button
                onClick={() => setCollapsed((c) => !c)}
                className="w-full flex items-center justify-between px-2 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-slate-400 hover:text-slate-600 transition-colors"
                data-testid={`nav-section-${group.section.toLowerCase()}`}
            >
                {group.section}
                <CaretDown size={10} className={`transition-transform ${collapsed ? "-rotate-90" : ""}`} />
            </button>
            <div className={`flex flex-col gap-0.5 overflow-hidden transition-all ${collapsed ? "max-h-0" : "max-h-[600px]"}`}>
                {group.items.map((item) => (
                    <NavLink
                        key={item.to}
                        to={item.to}
                        onClick={onItemClick}
                        end={item.to === "/app/dashboard"}
                        data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g,"-")}-link`}
                        className={({ isActive }) =>
                            `group flex items-center gap-3 pl-3 pr-2 py-1.5 text-sm font-medium rounded-lg transition-all duration-150 ${
                                isActive
                                    ? "bg-[#1D4ED8]/8 text-[#1D4ED8]"
                                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                            }`
                        }
                    >
                        {({ isActive }) => (
                            <>
                                <item.icon size={16} weight={isActive ? "fill" : "duotone"} />
                                <span className="truncate">{item.label}</span>
                            </>
                        )}
                    </NavLink>
                ))}
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
            toast.success(data.email_sent ? "Verification email sent" : "Verification link refreshed");
        } catch {
            toast.error("Could not resend");
        } finally { setResending(false); }
    };
    return (
        <div className="mb-6 p-3 rounded-lg border-l-4 border-amber-500 bg-amber-50 flex items-center justify-between gap-3" data-testid="verify-banner">
            <div className="flex items-center gap-2 text-sm text-amber-900">
                <EnvelopeSimple size={18} weight="duotone" />
                <span>Verify <strong>{user.email}</strong> to receive invoices and booking confirmations.</span>
            </div>
            <div className="flex items-center gap-2">
                <button onClick={resend} disabled={resending} data-testid="verify-resend-button"
                    className="text-xs font-semibold px-3 py-1.5 rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-60 transition-colors">
                    {resending ? "Sending..." : "Resend"}
                </button>
                <button onClick={() => setDismissed(true)} aria-label="Dismiss" className="p-1 rounded hover:bg-amber-100"><X size={16} /></button>
            </div>
        </div>
    );
}
