import { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { ChartLineUp, CurrencyDollar, Wrench, UsersThree, ArrowUpRight, Clock } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

const STATUS_COLORS = {
    unscheduled: "bg-slate-100 text-slate-700 border-slate-300",
    scheduled: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30",
    in_progress: "bg-amber-50 text-amber-700 border-amber-400",
    completed: "bg-emerald-50 text-emerald-700 border-emerald-400",
    cancelled: "bg-red-50 text-[#DC2626] border-[#DC2626]/40",
};

export default function Dashboard() {
    const { user } = useAuth();
    const [stats, setStats] = useState(null);
    const [recent, setRecent] = useState([]);

    useEffect(() => {
        api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
        api.get("/jobs").then((r) => setRecent(r.data.slice(0, 6))).catch(() => {});
    }, []);

    const kpis = [
        { label: "Jobs Today", value: stats?.jobs_today ?? "—", icon: Wrench, accent: "text-[#1D4ED8]" },
        { label: "Revenue Today", value: stats ? `$${stats.revenue_today.toFixed(0)}` : "—", icon: CurrencyDollar, accent: "text-emerald-600" },
        { label: "Active Technicians", value: stats?.active_technicians ?? "—", icon: UsersThree, accent: "text-[#DC2626]" },
        { label: "Completion Rate", value: stats ? `${stats.completion_rate}%` : "—", icon: ChartLineUp, accent: "text-slate-900" },
    ];

    return (
        <div data-testid="dashboard-page" className="space-y-10">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Operations</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">
                        Good {hourGreeting()}, {user?.name?.split(" ")[0]}.
                    </h1>
                    <p className="text-sm text-slate-500 mt-2">Here's how your crew is performing today.</p>
                </div>
                <Link
                    to="/app/jobs"
                    data-testid="dashboard-new-job-link"
                    className="bg-[#DC2626] text-white px-5 py-2.5 font-semibold hover:bg-[#B91C1C] transition-colors"
                >
                    + New Work Order
                </Link>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-slate-200 border border-slate-200">
                {kpis.map((k) => (
                    <div key={k.label} className="bg-white p-5" data-testid={`kpi-${k.label.toLowerCase().replace(/\s+/g,"-")}`}>
                        <div className="flex items-start justify-between">
                            <div className="overline">{k.label}</div>
                            <k.icon size={18} weight="duotone" className={k.accent} />
                        </div>
                        <div className="font-display text-3xl font-extrabold tracking-tighter mt-3">{k.value}</div>
                    </div>
                ))}
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 border border-slate-200">
                    <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
                        <h2 className="font-heading text-sm font-semibold uppercase tracking-wider">Recent Work Orders</h2>
                        <Link to="/app/jobs" className="text-xs text-[#1D4ED8] hover:underline flex items-center gap-1">
                            View all <ArrowUpRight size={14} />
                        </Link>
                    </div>
                    <div className="divide-y divide-slate-200">
                        {recent.length === 0 && (
                            <div className="p-8 text-center text-sm text-slate-500">No jobs yet. Create your first work order.</div>
                        )}
                        {recent.map((j) => (
                            <div key={j.id} className="px-5 py-4 flex items-center justify-between gap-4">
                                <div className="min-w-0">
                                    <div className="font-medium truncate" data-testid={`recent-job-title-${j.id}`}>{j.title}</div>
                                    <div className="text-xs text-slate-500 mt-0.5 truncate">
                                        {j.customer_name || "—"} · {j.address || "No address"}
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <div className="font-mono text-sm">${(j.price || 0).toFixed(0)}</div>
                                    <span className={`text-xs px-2 py-1 border ${STATUS_COLORS[j.status]}`}>
                                        {j.status.replace("_"," ")}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="border border-slate-200">
                    <div className="px-5 py-3 border-b border-slate-200">
                        <h2 className="font-heading text-sm font-semibold uppercase tracking-wider">Pipeline</h2>
                    </div>
                    <div className="p-5 space-y-4">
                        {stats?.totals && Object.entries(stats.totals).filter(([k]) => k !== "total").map(([k, v]) => (
                            <div key={k}>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="capitalize">{k.replace("_"," ")}</span>
                                    <span className="font-mono font-semibold">{v}</span>
                                </div>
                                <div className="h-1.5 bg-slate-100">
                                    <div
                                        className="h-full bg-[#1D4ED8]"
                                        style={{ width: `${stats.totals.total ? (v / stats.totals.total) * 100 : 0}%` }}
                                    />
                                </div>
                            </div>
                        ))}
                        <div className="pt-3 border-t border-slate-200 flex items-center gap-2 text-xs text-slate-500">
                            <Clock size={14} /> Refreshed live
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function hourGreeting() {
    const h = new Date().getHours();
    if (h < 12) return "morning";
    if (h < 18) return "afternoon";
    return "evening";
}
