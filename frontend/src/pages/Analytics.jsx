import { useEffect, useMemo, useState } from "react";
import api, { API_BASE, formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
    ChartLine, Users, Megaphone, Phone, Bank, UsersThree, Trophy,
    DownloadSimple, Calendar, CurrencyDollar, ArrowUp, ArrowDown,
} from "@phosphor-icons/react";

const fmt$ = (v) => `$${(Number(v) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const fmtPct = (v) => v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v}%`;

const TABS = [
    { key: "overview",   label: "Overview",   icon: ChartLine },
    { key: "revenue",    label: "Revenue",    icon: CurrencyDollar },
    { key: "techs",      label: "Technicians", icon: Users },
    { key: "marketing",  label: "Marketing",  icon: Megaphone },
    { key: "calls",      label: "Calls",      icon: Phone },
    { key: "financing",  label: "Financing",  icon: Bank },
    { key: "memberships",label: "Memberships", icon: UsersThree },
    { key: "leaderboard",label: "Leaderboard", icon: Trophy },
];

const PIE_COLORS = ["#1D4ED8", "#7C3AED", "#DC2626", "#F59E0B", "#10B981", "#0EA5E9", "#EC4899", "#64748B"];

export default function Analytics() {
    const [tab, setTab] = useState("overview");
    const today = new Date();
    const monthAgo = new Date(today.getTime() - 30 * 86400_000);
    const [start, setStart] = useState(monthAgo.toISOString().slice(0, 10));
    const [end, setEnd] = useState(today.toISOString().slice(0, 10));
    const [branchId, setBranchId] = useState("");
    const [branches, setBranches] = useState([]);

    useEffect(() => {
        api.get("/branches").then(({ data }) => setBranches(data)).catch(() => {});
    }, []);

    const params = useMemo(() => ({
        start: new Date(start).toISOString(),
        end: new Date(end + "T23:59:59").toISOString(),
        ...(branchId && { branch_id: branchId }),
    }), [start, end, branchId]);

    const downloadCsv = async (report) => {
        try {
            const url = `${API_BASE}/analytics/export.csv?report=${report}&start=${encodeURIComponent(params.start)}&end=${encodeURIComponent(params.end)}${branchId ? `&branch_id=${branchId}` : ""}`;
            const res = await fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` } });
            if (!res.ok) throw new Error("Export failed");
            const blob = await res.blob();
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = `${report}-${start}-to-${end}.csv`;
            a.click();
            toast.success("CSV downloaded");
        } catch (e) { toast.error("Export failed"); }
    };

    const TabIcon = TABS.find((t) => t.key === tab)?.icon || ChartLine;

    return (
        <div className="space-y-5 max-w-[1600px]">
            <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
                        <ChartLine size={28}/> Analytics
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">Executive-level KPIs across revenue, techs, marketing, calls, financing, and memberships.</p>
                </div>
                {/* Filters */}
                <div className="flex flex-wrap items-center gap-2">
                    <div className="inline-flex items-center gap-1 px-3 h-10 rounded-lg border border-slate-200 bg-white">
                        <Calendar size={14} className="text-slate-400"/>
                        <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="text-sm border-0 outline-none" data-testid="analytics-start"/>
                        <span className="text-slate-400 text-xs">→</span>
                        <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="text-sm border-0 outline-none" data-testid="analytics-end"/>
                    </div>
                    {branches.length > 0 && (
                        <select value={branchId} onChange={(e) => setBranchId(e.target.value)}
                            className="h-10 px-3 rounded-lg border border-slate-200 bg-white text-sm" data-testid="analytics-branch">
                            <option value="">All branches</option>
                            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                        </select>
                    )}
                    {["revenue","technicians","marketing","financing","leaderboard"].includes(tab === "techs" ? "technicians" : tab === "memberships" ? null : tab === "overview" ? null : tab) && (
                        <button onClick={() => downloadCsv(tab === "techs" ? "technicians" : tab)}
                            className="h-10 px-4 rounded-lg bg-slate-900 text-white text-sm font-bold inline-flex items-center gap-2"
                            data-testid="analytics-export-btn">
                            <DownloadSimple size={14}/> Export CSV
                        </button>
                    )}
                </div>
            </header>

            {/* Tab strip */}
            <div className="border-b border-slate-200 flex gap-1 overflow-x-auto">
                {TABS.map(({ key, label, icon: Icon }) => (
                    <button key={key} onClick={() => setTab(key)}
                        className={`pb-3 pt-1 px-3 text-sm font-semibold whitespace-nowrap inline-flex items-center gap-2 ${tab === key ? "border-b-2 border-[#1D4ED8] text-[#1D4ED8]" : "text-slate-500 hover:text-slate-700"}`}
                        data-testid={`analytics-tab-${key}`}>
                        <Icon size={14}/>{label}
                    </button>
                ))}
            </div>

            {tab === "overview"    && <Overview params={params}/>}
            {tab === "revenue"     && <Revenue params={params}/>}
            {tab === "techs"       && <Technicians params={params}/>}
            {tab === "marketing"   && <Marketing params={params}/>}
            {tab === "calls"       && <Calls params={params}/>}
            {tab === "financing"   && <Financing params={params}/>}
            {tab === "memberships" && <Memberships/>}
            {tab === "leaderboard" && <Leaderboard params={params}/>}
        </div>
    );
}

function Kpi({ label, value, delta, accent }) {
    return (
        <div className="bg-white border border-slate-200 rounded-2xl p-4">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">{label}</div>
            <div className={`text-3xl font-extrabold mt-1 ${accent || "text-slate-900"}`}>{value}</div>
            {delta !== undefined && delta !== null && (
                <div className={`text-xs mt-1 inline-flex items-center gap-1 ${delta >= 0 ? "text-green-600" : "text-rose-600"}`}>
                    {delta >= 0 ? <ArrowUp size={11}/> : <ArrowDown size={11}/>} {fmtPct(delta)} vs. prev period
                </div>
            )}
        </div>
    );
}

function Overview({ params }) {
    const [d, setD] = useState(null);
    const [rt, setRt] = useState(null);
    const [series, setSeries] = useState([]);

    useEffect(() => {
        api.get("/analytics/overview", { params }).then(({ data }) => setD(data));
        api.get("/analytics/revenue", { params: { ...params, granularity: "day" } }).then(({ data }) => setSeries(data.series));
        const tick = () => api.get("/analytics/realtime").then(({ data }) => setRt(data)).catch(() => {});
        tick();
        const t = setInterval(tick, 30_000);
        return () => clearInterval(t);
    }, [JSON.stringify(params)]); // eslint-disable-line

    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    return (
        <div className="space-y-5">
            {rt && (
                <div className="bg-gradient-to-r from-slate-900 to-slate-700 text-white rounded-2xl px-5 py-4 flex flex-wrap items-center gap-6" data-testid="realtime-banner">
                    <div className="text-xs uppercase tracking-wider opacity-70 font-bold">Live today</div>
                    <Pulse label="In progress" v={rt.jobs_in_progress}/>
                    <Pulse label="Completed" v={rt.jobs_completed_today}/>
                    <Pulse label="Revenue" v={fmt$(rt.revenue_today)}/>
                    <Pulse label="New finance apps" v={rt.new_finance_apps_today}/>
                    <Pulse label="Funded" v={rt.funded_today}/>
                    <div className="ml-auto text-[10px] opacity-60">refreshed {new Date(rt.as_of).toLocaleTimeString()}</div>
                </div>
            )}
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <Kpi label="Revenue" value={fmt$(d.revenue)} delta={d.revenue_delta_pct} accent="text-green-700"/>
                <Kpi label="Jobs completed" value={d.jobs_completed}/>
                <Kpi label="Avg ticket" value={fmt$(d.avg_ticket)}/>
                <Kpi label="Active customers" value={d.customers_active}/>
                <Kpi label="Finance funded" value={fmt$(d.finance_funded)} accent="text-violet-700"/>
                <Kpi label="Finance count" value={d.finance_funded_count}/>
                <Kpi label="Jobs total" value={d.jobs_total}/>
                <Kpi label="Jobs paid" value={d.jobs_paid}/>
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl p-5">
                <div className="text-sm font-bold mb-3">Revenue trend</div>
                <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={series}>
                        <defs><linearGradient id="r" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#1D4ED8" stopOpacity={0.4}/><stop offset="95%" stopColor="#1D4ED8" stopOpacity={0}/></linearGradient></defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/>
                        <XAxis dataKey="bucket" fontSize={11}/>
                        <YAxis fontSize={11}/>
                        <Tooltip formatter={(v) => fmt$(v)}/>
                        <Area type="monotone" dataKey="revenue" stroke="#1D4ED8" fill="url(#r)" strokeWidth={2}/>
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

function Pulse({ label, v }) {
    return (
        <div>
            <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
            <div className="text-xl font-extrabold">{v}</div>
        </div>
    );
}

function Revenue({ params }) {
    const [granularity, setGranularity] = useState("day");
    const [d, setD] = useState(null);
    useEffect(() => {
        api.get("/analytics/revenue", { params: { ...params, granularity } }).then(({ data }) => setD(data));
    }, [JSON.stringify(params), granularity]); // eslint-disable-line
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    return (
        <div className="space-y-3">
            <div className="inline-flex rounded-lg border border-slate-200 p-1 bg-white">
                {["day", "week", "month"].map((g) => (
                    <button key={g} onClick={() => setGranularity(g)} className={`px-3 py-1 text-xs font-bold rounded ${granularity === g ? "bg-slate-900 text-white" : "text-slate-600"}`} data-testid={`rev-gran-${g}`}>{g}</button>
                ))}
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl p-5">
                <ResponsiveContainer width="100%" height={360}>
                    <LineChart data={d.series}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/>
                        <XAxis dataKey="bucket" fontSize={11}/>
                        <YAxis yAxisId="left" fontSize={11}/>
                        <YAxis yAxisId="right" orientation="right" fontSize={11}/>
                        <Tooltip formatter={(v, name) => name === "revenue" ? fmt$(v) : v}/>
                        <Legend/>
                        <Line yAxisId="left" type="monotone" dataKey="revenue" stroke="#1D4ED8" strokeWidth={2}/>
                        <Line yAxisId="right" type="monotone" dataKey="jobs" stroke="#DC2626" strokeWidth={2}/>
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

function Technicians({ params }) {
    const [d, setD] = useState(null);
    useEffect(() => { api.get("/analytics/technicians", { params }).then(({ data }) => setD(data)); }, [JSON.stringify(params)]); // eslint-disable-line
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    return (
        <div className="space-y-5">
            <div className="bg-white border border-slate-200 rounded-2xl p-5">
                <div className="text-sm font-bold mb-3">Revenue by technician</div>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={d.techs.slice(0, 10)}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/>
                        <XAxis dataKey="name" fontSize={11} angle={-20} textAnchor="end" height={60}/>
                        <YAxis fontSize={11}/>
                        <Tooltip formatter={(v) => fmt$(v)}/>
                        <Bar dataKey="revenue" fill="#1D4ED8" radius={[6, 6, 0, 0]}/>
                    </BarChart>
                </ResponsiveContainer>
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                        <tr><th className="p-3 text-left">Tech</th><th className="p-3 text-right">Jobs</th><th className="p-3 text-right">Completed</th><th className="p-3 text-right">Rate</th><th className="p-3 text-right">Revenue</th><th className="p-3 text-right">Avg ★</th><th className="p-3 text-right">Tips</th></tr>
                    </thead>
                    <tbody>
                        {d.techs.map((t) => (
                            <tr key={t.tech_id} className="border-t border-slate-100" data-testid={`tech-row-${t.tech_id}`}>
                                <td className="p-3 font-bold">{t.name}<div className="text-[10px] text-slate-500">{t.role}</div></td>
                                <td className="p-3 text-right font-mono">{t.jobs_total}</td>
                                <td className="p-3 text-right font-mono">{t.jobs_completed}</td>
                                <td className="p-3 text-right">{t.completion_rate}%</td>
                                <td className="p-3 text-right font-mono font-bold">{fmt$(t.revenue)}</td>
                                <td className="p-3 text-right">{t.avg_rating || "—"}</td>
                                <td className="p-3 text-right font-mono">{fmt$(t.tips)}</td>
                            </tr>
                        ))}
                        {!d.techs.length && <tr><td colSpan={7} className="p-8 text-center text-slate-500">No tech data for window.</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function Marketing({ params }) {
    const [d, setD] = useState(null);
    useEffect(() => { api.get("/analytics/marketing", { params }).then(({ data }) => setD(data)); }, [JSON.stringify(params)]); // eslint-disable-line
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    const total = d.sources.reduce((s, r) => s + r.revenue, 0);
    return (
        <div className="grid lg:grid-cols-2 gap-5">
            <div className="bg-white border border-slate-200 rounded-2xl p-5">
                <div className="text-sm font-bold mb-3">Revenue by source</div>
                <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                        <Pie data={d.sources} dataKey="revenue" nameKey="source" outerRadius={100} label>
                            {d.sources.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]}/>)}
                        </Pie>
                        <Tooltip formatter={(v) => fmt$(v)}/>
                    </PieChart>
                </ResponsiveContainer>
                <div className="text-center text-xs text-slate-500 mt-2">Total revenue: <span className="font-bold">{fmt$(total)}</span></div>
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                        <tr><th className="p-3 text-left">Source</th><th className="p-3 text-right">Leads</th><th className="p-3 text-right">Won</th><th className="p-3 text-right">Conv.</th><th className="p-3 text-right">Revenue</th><th className="p-3 text-right">ROI</th></tr>
                    </thead>
                    <tbody>
                        {d.sources.map((s, i) => (
                            <tr key={s.source} className="border-t border-slate-100">
                                <td className="p-3 font-bold capitalize"><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}/>{s.source}</td>
                                <td className="p-3 text-right font-mono">{s.leads}</td>
                                <td className="p-3 text-right font-mono">{s.won}</td>
                                <td className="p-3 text-right">{s.conversion_rate}%</td>
                                <td className="p-3 text-right font-mono font-bold">{fmt$(s.revenue)}</td>
                                <td className="p-3 text-right font-mono">{s.roi_pct === null ? "—" : `${s.roi_pct}%`}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function Calls({ params }) {
    const [d, setD] = useState(null);
    useEffect(() => { api.get("/analytics/calls", { params }).then(({ data }) => setD(data)); }, [JSON.stringify(params)]); // eslint-disable-line
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    const funnel = [
        { step: "Inbound calls", v: d.calls_total, pct: 100 },
        { step: "Booked", v: d.booked, pct: d.book_rate_pct },
        { step: "Completed", v: d.completed, pct: d.close_rate_pct },
    ];
    return (
        <div className="space-y-5">
            <div className="grid sm:grid-cols-4 gap-3">
                <Kpi label="Inbound calls" value={d.calls_total}/>
                <Kpi label="Book rate" value={`${d.book_rate_pct}%`} accent="text-blue-700"/>
                <Kpi label="Close rate" value={`${d.close_rate_pct}%`} accent="text-green-700"/>
                <Kpi label="Avg ticket" value={fmt$(d.avg_ticket)}/>
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-3" data-testid="calls-funnel">
                {funnel.map((f, i) => (
                    <div key={f.step}>
                        <div className="flex items-center justify-between text-xs font-bold">
                            <span>{f.step}</span><span className="font-mono">{f.v} ({f.pct}%)</span>
                        </div>
                        <div className="mt-1 h-8 rounded-lg overflow-hidden bg-slate-100">
                            <div className="h-full transition-all" style={{ width: `${f.pct}%`, background: ["#1D4ED8", "#7C3AED", "#10B981"][i] }}/>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function Financing({ params }) {
    const [d, setD] = useState(null);
    useEffect(() => { api.get("/analytics/financing-conversion", { params }).then(({ data }) => setD(data)); }, [JSON.stringify(params)]); // eslint-disable-line
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    return (
        <div className="space-y-5">
            <div className="grid sm:grid-cols-4 gap-3">
                <Kpi label="Approval rate" value={`${d.approval_rate_pct}%`} accent="text-green-700"/>
                <Kpi label="Sign rate" value={`${d.sign_rate_pct}%`} accent="text-blue-700"/>
                <Kpi label="Fund rate" value={`${d.fund_rate_pct}%`} accent="text-violet-700"/>
                <Kpi label="Funded $" value={fmt$(d.funded_amount)}/>
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl p-5" data-testid="fin-funnel">
                <div className="text-sm font-bold mb-3">Application funnel</div>
                <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={d.funnel}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0"/>
                        <XAxis dataKey="step" fontSize={11}/>
                        <YAxis fontSize={11}/>
                        <Tooltip/>
                        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                            {d.funnel.map((_, i) => <Cell key={i} fill={["#1D4ED8", "#7C3AED", "#EC4899", "#10B981"][i]}/>)}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

function Memberships() {
    const [d, setD] = useState(null);
    useEffect(() => { api.get("/analytics/memberships").then(({ data }) => setD(data)); }, []);
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    return (
        <div className="grid sm:grid-cols-4 gap-3">
            <Kpi label="Active members" value={d.active} accent="text-green-700"/>
            <Kpi label="MRR" value={fmt$(d.mrr)} accent="text-violet-700"/>
            <Kpi label="Retention" value={`${d.retention_pct}%`}/>
            <Kpi label="Churn rate" value={`${d.churn_rate_pct}%`} accent={d.churn_rate_pct > 5 ? "text-rose-700" : "text-slate-900"}/>
            <Kpi label="New in 30d" value={d.new_30d}/>
            <Kpi label="Churned in 30d" value={d.churned_30d}/>
            <Kpi label="Paused" value={d.paused}/>
            <Kpi label="Cancelled (lifetime)" value={d.cancelled}/>
        </div>
    );
}

function Leaderboard({ params }) {
    const [metric, setMetric] = useState("revenue");
    const [d, setD] = useState(null);
    useEffect(() => {
        api.get("/analytics/leaderboard", { params: { ...params, metric } }).then(({ data }) => setD(data));
    }, [JSON.stringify(params), metric]); // eslint-disable-line
    if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
    return (
        <div className="space-y-3">
            <div className="inline-flex rounded-lg border border-slate-200 p-1 bg-white">
                {[["revenue","Revenue"],["jobs","Wins"],["rating","Rating"]].map(([k, l]) => (
                    <button key={k} onClick={() => setMetric(k)} className={`px-3 py-1 text-xs font-bold rounded ${metric === k ? "bg-slate-900 text-white" : "text-slate-600"}`} data-testid={`lb-metric-${k}`}>{l}</button>
                ))}
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                        <tr><th className="p-3 text-left">#</th><th className="p-3 text-left">Name</th><th className="p-3 text-right">Revenue</th><th className="p-3 text-right">Jobs</th><th className="p-3 text-right">Wins</th><th className="p-3 text-right">Win %</th><th className="p-3 text-right">Rating</th></tr>
                    </thead>
                    <tbody>
                        {d.leaderboard.map((r, i) => (
                            <tr key={r.user_id} className="border-t border-slate-100" data-testid={`lb-row-${i}`}>
                                <td className="p-3"><span className={`inline-block w-7 h-7 rounded-full text-center leading-7 text-xs font-bold ${i === 0 ? "bg-yellow-100 text-yellow-800" : i === 1 ? "bg-slate-200 text-slate-700" : i === 2 ? "bg-orange-100 text-orange-800" : "bg-slate-50 text-slate-500"}`}>{i + 1}</span></td>
                                <td className="p-3 font-bold">{r.name}<div className="text-[10px] text-slate-500">{r.role}</div></td>
                                <td className="p-3 text-right font-mono font-bold">{fmt$(r.revenue)}</td>
                                <td className="p-3 text-right font-mono">{r.jobs}</td>
                                <td className="p-3 text-right font-mono">{r.wins}</td>
                                <td className="p-3 text-right">{r.win_rate_pct}%</td>
                                <td className="p-3 text-right">{r.avg_rating || "—"}</td>
                            </tr>
                        ))}
                        {!d.leaderboard.length && <tr><td colSpan={7} className="p-8 text-center text-slate-500">No data for window.</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
