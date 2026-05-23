import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Bank, CurrencyDollar, ChartBar, Gavel, X } from "@phosphor-icons/react";

const fmt$ = (v) => `$${(Number(v) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const TIER_COLORS = { excellent: "bg-green-100 text-green-800", good: "bg-blue-100 text-blue-800", fair: "bg-amber-100 text-amber-800", subprime: "bg-rose-100 text-rose-800", declined: "bg-slate-300 text-slate-700" };

export default function FinancingAdmin() {
    const [metrics, setMetrics] = useState(null);
    const [apps, setApps] = useState([]);
    const [filter, setFilter] = useState("");
    const [override, setOverride] = useState(null);

    const load = async () => {
        try {
            const [{ data: m }, { data: a }] = await Promise.all([
                api.get("/financing/admin/metrics"),
                api.get("/financing/admin/applications", { params: filter ? { status: filter } : {} }),
            ]);
            setMetrics(m); setApps(a);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { load(); }, [filter]);

    return (
        <div className="space-y-5 max-w-7xl">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2"><Bank size={28}/> Financing — Admin</h1>
                <p className="text-sm text-slate-500 mt-1">Platform-wide application volume + manual decision overrides.</p>
            </header>

            {metrics && (
                <div className="grid sm:grid-cols-4 gap-3" data-testid="fin-admin-metrics">
                    <Tile label="Total funded" value={fmt$(metrics.total_funded)} icon={CurrencyDollar} color="text-green-700"/>
                    <Tile label="Funding events" value={metrics.funding_events} icon={ChartBar} color="text-blue-700"/>
                    <Tile label="Tiers approved" value={Object.entries(metrics.by_tier || {}).filter(([k])=>k!=="declined").reduce((s,[,v])=>s+v,0)} icon={Gavel} color="text-violet-700"/>
                    <div className="bg-white border border-slate-200 rounded-2xl p-4">
                        <div className="text-[10px] uppercase tracking-wider text-slate-500">Volume by tier</div>
                        <div className="flex flex-wrap gap-1 mt-2">
                            {Object.entries(metrics.by_tier || {}).map(([k, v]) => (
                                <span key={k} className={`text-[11px] font-bold px-2 py-0.5 rounded ${TIER_COLORS[k] || "bg-slate-200"}`}>{k}:{v}</span>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {metrics?.by_status && (
                <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                    {Object.entries(metrics.by_status).map(([k, v]) => (
                        <div key={k} className="bg-white border border-slate-200 rounded-xl p-3">
                            <div className="text-2xl font-extrabold">{v.count}</div>
                            <div className="text-[10px] uppercase text-slate-500">{k.replace(/_/g," ")}</div>
                            <div className="text-[10px] font-mono text-slate-400 mt-1">{fmt$(v.amount)}</div>
                        </div>
                    ))}
                </div>
            )}

            <div className="flex items-center gap-2">
                <select value={filter} onChange={(e) => setFilter(e.target.value)} className="h-10 px-3 rounded-lg border border-slate-300 text-sm" data-testid="fin-admin-filter">
                    <option value="">All statuses</option>
                    {["started","decisioned","signed","funded","declined","manual_review"].map((s) => <option key={s}>{s}</option>)}
                </select>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                        <tr><th className="p-3 text-left">Customer</th><th className="p-3 text-left">Company</th><th className="p-3 text-right">Amount</th><th className="p-3 text-left">Status</th><th className="p-3 text-left">Tier</th><th className="p-3 text-left">Offer</th><th></th></tr>
                    </thead>
                    <tbody>
                        {apps.map((a) => (
                            <tr key={a.id} className="border-t border-slate-100" data-testid={`fin-admin-row-${a.id}`}>
                                <td className="p-3"><div className="font-bold">{a.customer_name}</div><div className="text-[10px] text-slate-500">{a.customer_email}</div></td>
                                <td className="p-3 text-xs text-slate-500 truncate max-w-[150px]">{a.company_id?.slice(0, 8)}</td>
                                <td className="p-3 text-right font-mono">{fmt$(a.amount)}</td>
                                <td className="p-3"><span className="text-xs font-bold">{a.status}</span></td>
                                <td className="p-3">{a.tier?.label && <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${TIER_COLORS[a.tier.label]}`}>{a.tier.label}</span>}</td>
                                <td className="p-3 text-xs">{a.offer ? `${a.offer.apr}% · ${a.offer.term_months}mo` : "—"}</td>
                                <td className="p-3 text-right">
                                    <button onClick={() => setOverride(a)} className="text-xs font-semibold px-3 py-1 rounded border border-slate-300 hover:bg-slate-50" data-testid={`fin-admin-override-${a.id}`}>Override</button>
                                </td>
                            </tr>
                        ))}
                        {!apps.length && <tr><td colSpan={7} className="p-8 text-center text-slate-500">No applications.</td></tr>}
                    </tbody>
                </table>
            </div>

            {override && <OverrideModal app={override} onClose={() => setOverride(null)} onSaved={load}/>}
        </div>
    );
}

function Tile({ label, value, icon: Icon, color }) {
    return (
        <div className="bg-white border border-slate-200 rounded-2xl p-4 flex items-center gap-3">
            <Icon size={32} weight="duotone" className={color || "text-slate-700"}/>
            <div><div className="text-2xl font-extrabold text-slate-900">{value}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div></div>
        </div>
    );
}

function OverrideModal({ app, onClose, onSaved }) {
    const [decision, setDecision] = useState(app.decision || "approved");
    const [apr, setApr] = useState(app.offer?.apr || 9.99);
    const [term, setTerm] = useState(app.offer?.term_months || 36);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);
    const save = async () => {
        setBusy(true);
        try {
            await api.patch(`/financing/admin/applications/${app.id}/decision`, { decision, apr: Number(apr), term_months: Number(term), reason });
            toast.success("Override saved");
            onSaved(); onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };
    return (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-3" onClick={(e) => e.stopPropagation()} data-testid="fin-override-modal">
                <div className="flex items-center justify-between"><h2 className="font-bold">Override decision</h2><button onClick={onClose}><X size={20}/></button></div>
                <div className="text-xs text-slate-500">{app.customer_name} · {fmt$(app.amount)}</div>
                <label className="text-xs block">Decision
                    <select value={decision} onChange={(e) => setDecision(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="override-decision">
                        {["approved","counter_offer","manual_review","declined"].map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                </label>
                <div className="grid grid-cols-2 gap-2">
                    <label className="text-xs block">APR<input type="number" step="0.01" value={apr} onChange={(e) => setApr(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1"/></label>
                    <label className="text-xs block">Term (months)<input type="number" value={term} onChange={(e) => setTerm(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1"/></label>
                </div>
                <label className="text-xs block">Reason<textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className="w-full px-3 py-2 rounded border border-slate-300 text-sm mt-1"/></label>
                <button onClick={save} disabled={busy} className="w-full px-4 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold disabled:opacity-50" data-testid="override-save">{busy ? "Saving…" : "Save override"}</button>
            </div>
        </div>
    );
}
