import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, FileText, CheckCircle, ClockClockwise, X, ArrowSquareOut } from "@phosphor-icons/react";

const STATUS_META = {
    draft:     { label: "Draft",     cls: "bg-slate-100 text-slate-700 border-slate-300" },
    sent:      { label: "Sent",      cls: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30" },
    viewed:    { label: "Viewed",    cls: "bg-indigo-50 text-indigo-700 border-indigo-300" },
    approved:  { label: "Approved",  cls: "bg-emerald-50 text-emerald-700 border-emerald-400" },
    declined:  { label: "Declined",  cls: "bg-red-50 text-[#DC2626] border-[#DC2626]/40" },
    expired:   { label: "Expired",   cls: "bg-amber-50 text-amber-700 border-amber-400" },
    converted: { label: "Converted", cls: "bg-violet-50 text-violet-700 border-violet-300" },
};

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }
function fmtDate(iso) { return iso ? new Date(iso).toLocaleDateString() : "—"; }

export default function Estimates() {
    const navigate = useNavigate();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");

    const load = async () => {
        try {
            const { data } = await api.get("/estimates");
            setItems(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []);

    const filtered = filter === "all" ? items : items.filter((e) => e.status === filter);

    const summary = {
        outstanding: items.filter((e) => ["sent","viewed"].includes(e.status))
            .reduce((s,e) => s + Math.max(...Object.values(e.totals_by_tier||{}).map(t=>t.total||0), 0), 0),
        approved: items.filter((e) => e.status === "approved")
            .reduce((s,e) => s + (e.totals_by_tier?.[e.selected_tier]?.total || 0), 0),
        approvedCount: items.filter((e) => ["approved","converted"].includes(e.status)).length,
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Estimates</h1>
                    <p className="text-sm text-slate-500">Good / Better / Best proposals with e-signature.</p>
                </div>
                <button
                    onClick={() => navigate("/app/estimates/new")}
                    className="inline-flex items-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-semibold px-4 py-2.5 rounded-lg shadow-sm transition"
                    data-testid="new-estimate-button"
                >
                    <Plus size={18} weight="bold" /> New Estimate
                </button>
            </div>

            {/* KPI cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Outstanding</div>
                    <div className="mt-1 text-3xl font-extrabold text-slate-900">{fmtMoney(summary.outstanding)}</div>
                    <div className="mt-1 text-xs text-slate-500">Top-tier value of sent/viewed estimates</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Approved</div>
                    <div className="mt-1 text-3xl font-extrabold text-emerald-600">{fmtMoney(summary.approved)}</div>
                    <div className="mt-1 text-xs text-slate-500">{summary.approvedCount} signed</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Total estimates</div>
                    <div className="mt-1 text-3xl font-extrabold text-slate-900">{items.length}</div>
                    <div className="mt-1 text-xs text-slate-500">All time</div>
                </div>
            </div>

            {/* Filter tabs */}
            <div className="flex flex-wrap items-center gap-2">
                {["all","draft","sent","viewed","approved","declined","converted"].map((s) => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`px-3 py-1.5 text-sm font-medium rounded-full border transition ${
                            filter === s
                                ? "bg-slate-900 text-white border-slate-900"
                                : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                        }`}
                        data-testid={`filter-${s}`}
                    >
                        {s === "all" ? "All" : STATUS_META[s]?.label || s}
                    </button>
                ))}
            </div>

            {/* List */}
            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : filtered.length === 0 ? (
                <div className="text-center py-16 rounded-2xl border-2 border-dashed border-slate-200">
                    <FileText size={48} className="mx-auto text-slate-300" />
                    <p className="mt-3 text-slate-500">No estimates yet. Create your first proposal.</p>
                </div>
            ) : (
                <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
                    <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                            <tr>
                                <th className="px-4 py-3 text-left">Number</th>
                                <th className="px-4 py-3 text-left">Title / Customer</th>
                                <th className="px-4 py-3 text-left">Status</th>
                                <th className="px-4 py-3 text-right">Range</th>
                                <th className="px-4 py-3 text-right">Selected</th>
                                <th className="px-4 py-3 text-left">Created</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((e) => {
                                const totals = e.totals_by_tier || {};
                                const values = Object.values(totals).map((t) => t.total || 0);
                                const min = values.length ? Math.min(...values) : 0;
                                const max = values.length ? Math.max(...values) : 0;
                                const meta = STATUS_META[e.status] || STATUS_META.draft;
                                const selectedTotal = e.selected_tier ? totals[e.selected_tier]?.total : null;
                                return (
                                    <tr
                                        key={e.id}
                                        className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                                        onClick={() => navigate(`/app/estimates/${e.id}`)}
                                        data-testid={`estimate-row-${e.id}`}
                                    >
                                        <td className="px-4 py-3 font-mono text-xs font-bold text-slate-700">{e.number}</td>
                                        <td className="px-4 py-3">
                                            <div className="font-semibold text-slate-900">{e.title}</div>
                                            <div className="text-xs text-slate-500">{e.customer_name || "—"}</div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${meta.cls}`}>
                                                {meta.label}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right font-semibold text-slate-700">
                                            {values.length ? `${fmtMoney(min)} – ${fmtMoney(max)}` : "—"}
                                        </td>
                                        <td className="px-4 py-3 text-right font-bold text-emerald-700">
                                            {selectedTotal != null ? fmtMoney(selectedTotal) : "—"}
                                        </td>
                                        <td className="px-4 py-3 text-xs text-slate-500">{fmtDate(e.created_at)}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
