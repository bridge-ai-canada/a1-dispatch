import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Buildings, MagnifyingGlass, DownloadSimple, Pause, Play, Trash, ChartBar } from "@phosphor-icons/react";

const PLAN_COLORS = { basic: "bg-slate-200 text-slate-800", team: "bg-blue-100 text-blue-800", business: "bg-violet-100 text-violet-800", pro: "bg-amber-100 text-amber-800", enterprise: "bg-rose-100 text-rose-800" };

export default function SuperTenants() {
    const [tenants, setTenants] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [search, setSearch] = useState("");
    const [planFilter, setPlanFilter] = useState("");
    const [loading, setLoading] = useState(true);

    const load = async () => {
        setLoading(true);
        try {
            const [{ data: t }, { data: m }] = await Promise.all([
                api.get("/tenants", { params: { q: search || undefined, plan: planFilter || undefined } }),
                api.get("/tenants/_/metrics"),
            ]);
            setTenants(t);
            setMetrics(m);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [planFilter]);

    const toggleStatus = async (c) => {
        const next = c.subscription?.status === "suspended" ? "active" : "suspended";
        if (next === "suspended" && !confirm(`Suspend ${c.name}? Their users will be locked out.`)) return;
        try {
            await api.patch(`/tenants/${c.id}/status`, { status: next });
            toast.success(`Tenant ${next}`);
            await load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const remove = async (c) => {
        if (!confirm(`PERMANENTLY DELETE ${c.name} and ALL its data? This cannot be undone.`)) return;
        if (!confirm(`Type confirmation: are you absolutely sure?`)) return;
        try {
            await api.delete(`/tenants/${c.id}`);
            toast.success("Tenant deleted");
            await load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const exportData = async (c) => {
        try {
            const { data } = await api.get(`/tenants/${c.id}/export`, { responseType: "blob" });
            const url = URL.createObjectURL(new Blob([data], { type: "application/json" }));
            const a = document.createElement("a"); a.href = url; a.download = `tenant-${c.id}.json`; a.click();
            toast.success("Export downloaded");
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    return (
        <div className="space-y-5 max-w-7xl">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Tenant management</h1>
                <p className="text-sm text-slate-500 mt-1">Platform-wide view of all companies. Suspend, export, or remove tenants.</p>
            </header>

            {/* Platform metrics */}
            {metrics && (
                <div className="grid sm:grid-cols-4 gap-3" data-testid="platform-metrics">
                    <div className="bg-white border border-slate-200 rounded-2xl p-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500">Tenants</div>
                        <div className="text-3xl font-extrabold text-slate-900">{metrics.tenants_total}</div>
                        <div className="text-xs text-slate-500 mt-1">{metrics.tenants_active} active · {metrics.tenants_suspended} suspended</div>
                    </div>
                    <div className="bg-white border border-slate-200 rounded-2xl p-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500">MRR</div>
                        <div className="text-3xl font-extrabold text-green-700">${metrics.mrr_usd.toLocaleString()}</div>
                        <div className="text-xs text-slate-500 mt-1">Monthly recurring</div>
                    </div>
                    <div className="bg-white border border-slate-200 rounded-2xl p-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500">ARR</div>
                        <div className="text-3xl font-extrabold text-slate-900">${metrics.arr_usd.toLocaleString()}</div>
                        <div className="text-xs text-slate-500 mt-1">Annual run rate</div>
                    </div>
                    <div className="bg-white border border-slate-200 rounded-2xl p-4">
                        <div className="text-xs uppercase tracking-wider text-slate-500">By plan</div>
                        <div className="flex flex-wrap gap-1 mt-2">
                            {Object.entries(metrics.by_plan || {}).map(([k, v]) => (
                                <span key={k} className={`text-xs font-bold px-2 py-1 rounded ${PLAN_COLORS[k] || PLAN_COLORS.basic}`}>{k}: {v}</span>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1 max-w-sm">
                    <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
                    <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()}
                        placeholder="Search company name…"
                        className="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-300 text-sm" data-testid="tenant-search"/>
                </div>
                <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-300 text-sm" data-testid="tenant-plan-filter">
                    <option value="">All plans</option>
                    <option value="basic">Basic</option>
                    <option value="team">Team</option>
                    <option value="business">Business</option>
                    <option value="pro">Pro</option>
                    <option value="enterprise">Enterprise</option>
                </select>
            </div>

            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : (
                <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                            <tr>
                                <th className="text-left p-3">Company</th>
                                <th className="text-left p-3">Plan</th>
                                <th className="text-left p-3">Status</th>
                                <th className="text-right p-3">Users</th>
                                <th className="text-right p-3">Jobs</th>
                                <th className="text-right p-3">Revenue</th>
                                <th className="text-right p-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {tenants.map((c) => {
                                const status = c.subscription?.status || "active";
                                const plan = c.subscription?.plan || "basic";
                                return (
                                    <tr key={c.id} className="border-t border-slate-100" data-testid={`tenant-row-${c.id}`}>
                                        <td className="p-3">
                                            <div className="font-bold text-slate-900">{c.name || "—"}</div>
                                            <div className="text-[10px] text-slate-500">{c.industry || ""} · {c.id.slice(0, 8)}</div>
                                        </td>
                                        <td className="p-3"><span className={`text-xs font-bold px-2 py-1 rounded ${PLAN_COLORS[plan] || PLAN_COLORS.basic}`}>{plan}</span></td>
                                        <td className="p-3"><span className={`text-xs font-bold ${status === "suspended" ? "text-rose-700" : "text-green-700"}`}>{status}</span></td>
                                        <td className="p-3 text-right font-mono">{c.users_count || 0}</td>
                                        <td className="p-3 text-right font-mono">{c.jobs_count || 0}</td>
                                        <td className="p-3 text-right font-mono">${(c.paid_revenue || 0).toLocaleString()}</td>
                                        <td className="p-3 text-right">
                                            <div className="inline-flex gap-1">
                                                <button onClick={() => toggleStatus(c)} className="p-2 rounded hover:bg-slate-100" title={status === "suspended" ? "Activate" : "Suspend"} data-testid={`tenant-toggle-${c.id}`}>
                                                    {status === "suspended" ? <Play size={14}/> : <Pause size={14}/>}
                                                </button>
                                                <button onClick={() => exportData(c)} className="p-2 rounded hover:bg-slate-100" title="Export data" data-testid={`tenant-export-${c.id}`}><DownloadSimple size={14}/></button>
                                                <button onClick={() => remove(c)} className="p-2 rounded hover:bg-rose-50 text-rose-700" title="Delete" data-testid={`tenant-delete-${c.id}`}><Trash size={14}/></button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                            {!tenants.length && (
                                <tr><td colSpan={7} className="p-8 text-center text-slate-500"><Buildings size={36} className="mx-auto text-slate-300 mb-2"/>No tenants found.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
