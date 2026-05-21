import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, Receipt } from "@phosphor-icons/react";

const STATUS_META = {
    draft:   { label: "Draft",   cls: "bg-slate-100 text-slate-700 border-slate-300" },
    sent:    { label: "Sent",    cls: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30" },
    viewed:  { label: "Viewed",  cls: "bg-indigo-50 text-indigo-700 border-indigo-300" },
    partial: { label: "Partial", cls: "bg-amber-50 text-amber-700 border-amber-400" },
    paid:    { label: "Paid",    cls: "bg-emerald-50 text-emerald-700 border-emerald-400" },
    overdue: { label: "Overdue", cls: "bg-red-50 text-[#DC2626] border-[#DC2626]/40" },
    void:    { label: "Void",    cls: "bg-slate-100 text-slate-500 border-slate-300" },
};

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }
function fmtDate(iso) { return iso ? new Date(iso).toLocaleDateString() : "—"; }

export default function Invoices() {
    const navigate = useNavigate();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");

    useEffect(() => {
        api.get("/invoices").then((r) => setItems(r.data))
            .catch((e) => toast.error(formatApiError(e.response?.data?.detail)))
            .finally(() => setLoading(false));
    }, []);

    const filtered = filter === "all" ? items : items.filter((i) => i.status === filter);
    const summary = {
        outstanding: items.filter((i) => !["paid","void"].includes(i.status))
            .reduce((s,i) => s + (i.balance_due || 0), 0),
        paid: items.filter((i) => i.status === "paid")
            .reduce((s,i) => s + (i.totals?.total || 0), 0),
        overdue: items.filter((i) => i.status === "overdue")
            .reduce((s,i) => s + (i.balance_due || 0), 0),
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Invoices</h1>
                    <p className="text-sm text-slate-500">Bill customers and accept online payments.</p>
                </div>
                <button onClick={() => navigate("/app/invoices/new")}
                    className="inline-flex items-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-semibold px-4 py-2.5 rounded-lg shadow-sm"
                    data-testid="new-invoice-button">
                    <Plus size={18} weight="bold"/> New Invoice
                </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Outstanding</div>
                    <div className="mt-1 text-3xl font-extrabold text-slate-900">{fmtMoney(summary.outstanding)}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Overdue</div>
                    <div className="mt-1 text-3xl font-extrabold text-[#DC2626]">{fmtMoney(summary.overdue)}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Paid (lifetime)</div>
                    <div className="mt-1 text-3xl font-extrabold text-emerald-600">{fmtMoney(summary.paid)}</div>
                </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
                {["all","draft","sent","viewed","partial","paid","overdue"].map((s) => (
                    <button key={s} onClick={() => setFilter(s)}
                        className={`px-3 py-1.5 text-sm font-medium rounded-full border transition ${
                            filter === s ? "bg-slate-900 text-white border-slate-900"
                                : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                        }`}
                        data-testid={`filter-${s}`}>
                        {s === "all" ? "All" : STATUS_META[s]?.label || s}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : filtered.length === 0 ? (
                <div className="text-center py-16 rounded-2xl border-2 border-dashed border-slate-200">
                    <Receipt size={48} className="mx-auto text-slate-300"/>
                    <p className="mt-3 text-slate-500">No invoices yet.</p>
                </div>
            ) : (
                <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
                    <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-slate-600 text-xs uppercase tracking-wider">
                            <tr>
                                <th className="px-4 py-3 text-left">Number</th>
                                <th className="px-4 py-3 text-left">Customer</th>
                                <th className="px-4 py-3 text-left">Status</th>
                                <th className="px-4 py-3 text-right">Total</th>
                                <th className="px-4 py-3 text-right">Balance</th>
                                <th className="px-4 py-3 text-left">Due</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((inv) => {
                                const meta = STATUS_META[inv.status] || STATUS_META.draft;
                                return (
                                    <tr key={inv.id} onClick={() => navigate(`/app/invoices/${inv.id}`)}
                                        className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                                        data-testid={`invoice-row-${inv.id}`}>
                                        <td className="px-4 py-3 font-mono text-xs font-bold text-slate-700">{inv.number}</td>
                                        <td className="px-4 py-3">
                                            <div className="font-semibold text-slate-900">{inv.customer_name || "—"}</div>
                                            <div className="text-xs text-slate-500">{inv.title}</div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${meta.cls}`}>
                                                {meta.label}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right font-semibold text-slate-900">{fmtMoney(inv.totals?.total)}</td>
                                        <td className="px-4 py-3 text-right font-bold text-[#DC2626]">{fmtMoney(inv.balance_due)}</td>
                                        <td className="px-4 py-3 text-xs text-slate-500">{fmtDate(inv.due_at)}</td>
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
