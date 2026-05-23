import { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { ChartLineUp, CurrencyDollar, Wrench, UsersThree, ArrowUpRight, Clock, Star, Crown, ArrowsClockwise } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

const STATUS_COLORS = {
    new_lead: "bg-sky-50 text-sky-700 border-sky-300",
    contacted: "bg-cyan-50 text-cyan-700 border-cyan-300",
    qualified: "bg-teal-50 text-teal-700 border-teal-300",
    quote_sent: "bg-violet-50 text-violet-700 border-violet-300",
    unscheduled: "bg-slate-100 text-slate-700 border-slate-300",
    won_bid: "bg-violet-50 text-violet-700 border-violet-400",
    lost_bid: "bg-rose-50 text-rose-700 border-rose-300",
    on_hold: "bg-orange-50 text-orange-700 border-orange-400",
    scheduled_installation: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30",
    scheduled: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30",
    in_progress: "bg-amber-50 text-amber-700 border-amber-400",
    completed: "bg-emerald-50 text-emerald-700 border-emerald-400",
    cancelled: "bg-red-50 text-[#DC2626] border-[#DC2626]/40",
};

export default function Dashboard() {
    const { user } = useAuth();
    const [stats, setStats] = useState(null);
    const [recent, setRecent] = useState([]);
    const [leaderboard, setLeaderboard] = useState([]);
    const [forecast, setForecast] = useState(null);

    useEffect(() => {
        api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
        api.get("/jobs").then((r) => setRecent(r.data.slice(0, 6))).catch(() => {});
        api.get("/dashboard/leaderboard").then((r) => setLeaderboard(r.data)).catch(() => {});
        api.get("/dashboard/recurring-forecast").then((r) => setForecast(r.data)).catch(() => {});
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Tech Leaderboard */}
                <div className="border border-slate-200" data-testid="dashboard-leaderboard">
                    <div className="px-5 py-3 border-b border-slate-200 flex items-center gap-2">
                        <Crown size={14} weight="duotone" className="text-amber-500" />
                        <h2 className="font-heading text-sm font-semibold uppercase tracking-wider">Tech Leaderboard · 30d</h2>
                    </div>
                    <div className="p-5">
                        {leaderboard.length === 0 ? (
                            <div className="text-sm text-slate-500 py-6 text-center">
                                No ratings yet. Customers rate jobs from the portal.
                            </div>
                        ) : (
                            <ol className="space-y-3">
                                {leaderboard.slice(0, 5).map((t, idx) => (
                                    <li key={t.tech_id} className="flex items-center gap-3" data-testid={`leaderboard-row-${t.tech_id}`}>
                                        <div className="w-6 text-center font-display font-extrabold text-slate-400">{idx + 1}</div>
                                        <div className="flex-1 min-w-0">
                                            <div className="font-semibold truncate">{t.name}</div>
                                            <div className="text-[11px] text-slate-500">{t.ratings_count} rating{t.ratings_count === 1 ? "" : "s"} · ${t.revenue.toFixed(0)} revenue</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="flex items-center gap-1 justify-end">
                                                <Star size={14} weight="fill" className="text-amber-400" />
                                                <span className="font-mono font-bold">{t.rating_avg.toFixed(1)}</span>
                                            </div>
                                            {t.tip_total > 0 && (
                                                <div className="text-[10px] text-emerald-600 font-semibold">+${t.tip_total.toFixed(0)} tips</div>
                                            )}
                                        </div>
                                    </li>
                                ))}
                            </ol>
                        )}
                    </div>
                </div>

                {/* Recurring revenue forecast */}
                <div className="border border-slate-200" data-testid="dashboard-forecast">
                    <div className="px-5 py-3 border-b border-slate-200 flex items-center gap-2">
                        <ArrowsClockwise size={14} weight="duotone" className="text-emerald-600" />
                        <h2 className="font-heading text-sm font-semibold uppercase tracking-wider">Recurring Revenue · 30d Forecast</h2>
                    </div>
                    <div className="p-5">
                        <div className="grid grid-cols-2 gap-4 mb-5">
                            <div>
                                <div className="overline">Expected (30d)</div>
                                <div className="font-display text-3xl font-extrabold tracking-tighter mt-1">
                                    ${forecast?.total_expected?.toLocaleString() || "0"}
                                </div>
                            </div>
                            <div>
                                <div className="overline">Annual run-rate</div>
                                <div className="font-display text-3xl font-extrabold tracking-tighter mt-1 text-emerald-600">
                                    ${forecast?.annual_contract_value?.toLocaleString() || "0"}
                                </div>
                            </div>
                        </div>
                        <div className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold mb-2">
                            Top plans · {forecast?.active_plans || 0} active
                        </div>
                        {forecast?.plans?.length ? (
                            <ul className="space-y-2">
                                {forecast.plans.slice(0, 5).map((p) => (
                                    <li key={p.id} className="flex items-center justify-between text-sm" data-testid={`forecast-row-${p.id}`}>
                                        <div className="min-w-0">
                                            <div className="font-medium truncate">{p.title}</div>
                                            <div className="text-[11px] text-slate-500">{p.cadence} · {p.occurrences}× in 30d</div>
                                        </div>
                                        <div className="font-mono font-semibold">${p.expected_revenue.toFixed(0)}</div>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <div className="text-sm text-slate-500 py-2 text-center">
                                No recurring plans yet. <Link to="/app/recurring" className="text-[#1D4ED8] font-semibold">Create one →</Link>
                            </div>
                        )}
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
