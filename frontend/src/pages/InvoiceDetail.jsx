import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { formatApiError, API_BASE } from "../lib/api";
import { toast } from "sonner";
import {
    ArrowLeft, PaperPlaneTilt, FilePdf, PencilSimple, Link as LinkIcon,
    CheckCircle, CreditCard, Clock, Coins,
} from "@phosphor-icons/react";

const STATUS_META = {
    draft:   { label: "Draft",   cls: "bg-slate-100 text-slate-700 border-slate-300" },
    sent:    { label: "Sent",    cls: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30" },
    viewed:  { label: "Viewed",  cls: "bg-indigo-50 text-indigo-700 border-indigo-300" },
    partial: { label: "Partial", cls: "bg-amber-50 text-amber-700 border-amber-400" },
    paid:    { label: "Paid",    cls: "bg-emerald-50 text-emerald-700 border-emerald-400" },
    overdue: { label: "Overdue", cls: "bg-red-50 text-[#DC2626] border-[#DC2626]/40" },
};

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }

export default function InvoiceDetail() {
    const navigate = useNavigate();
    const { id } = useParams();
    const [doc, setDoc] = useState(null);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);

    const load = () => api.get(`/invoices/${id}`).then((r) => setDoc(r.data))
        .catch((e) => toast.error(formatApiError(e.response?.data?.detail)))
        .finally(() => setLoading(false));
    useEffect(() => { load(); }, [id]);

    const send = async () => {
        setBusy(true);
        try {
            const r = await api.post(`/invoices/${id}/send`);
            toast.success("Invoice sent");
            if (r.data.link) {
                await navigator.clipboard?.writeText(r.data.link).catch(()=>{});
                toast.message("Link copied", { description: r.data.link });
            }
            load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };

    const checkout = async (payType) => {
        try {
            const r = await api.post(`/invoices/${id}/checkout`, {
                origin_url: window.location.origin,
                pay_type: payType,
            });
            window.location.href = r.data.url;
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const copyLink = async () => {
        if (!doc?.public_token) return;
        const link = `${window.location.origin}/pay/${doc.public_token}`;
        await navigator.clipboard.writeText(link);
        toast.success("Customer payment link copied");
    };

    if (loading) return <div className="text-sm text-slate-500">Loading…</div>;
    if (!doc) return null;

    const meta = STATUS_META[doc.status] || STATUS_META.draft;
    const totals = doc.totals || {};
    const paid = doc.paid_amount || 0;
    const balance = doc.balance_due || 0;
    const canEdit = doc.status !== "paid";

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                    <button onClick={() => navigate("/app/invoices")} className="p-2 -ml-2 text-slate-600 hover:text-slate-900">
                        <ArrowLeft size={20}/>
                    </button>
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-bold text-slate-500">{doc.number}</span>
                            <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${meta.cls}`}>
                                {meta.label}
                            </span>
                        </div>
                        <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900">{doc.title}</h1>
                        <div className="text-sm text-slate-500">For <b>{doc.customer_name || "—"}</b> · {doc.customer_email || ""}</div>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    {canEdit && (
                        <button onClick={() => navigate(`/app/invoices/${id}/edit`)}
                            className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-3 py-2 rounded-lg font-semibold text-sm text-slate-700"
                            data-testid="edit-invoice-button">
                            <PencilSimple size={16}/> Edit
                        </button>
                    )}
                    <a href={`${API_BASE}/invoices/${id}/pdf`} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-3 py-2 rounded-lg font-semibold text-sm text-slate-700">
                        <FilePdf size={16}/> PDF
                    </a>
                    {doc.public_token && (
                        <button onClick={copyLink}
                            className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-3 py-2 rounded-lg font-semibold text-sm text-slate-700"
                            data-testid="copy-pay-link-button">
                            <LinkIcon size={16}/> Pay link
                        </button>
                    )}
                    {canEdit && (
                        <button onClick={send} disabled={busy || !doc.customer_email}
                            className="inline-flex items-center gap-2 bg-[#1D4ED8] hover:bg-[#1E40AF] text-white px-3 py-2 rounded-lg font-semibold text-sm shadow-sm"
                            data-testid="send-invoice-button">
                            <PaperPlaneTilt size={16} weight="fill"/> Send
                        </button>
                    )}
                </div>
            </div>

            {/* Summary card */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Total</div>
                    <div className="mt-1 text-3xl font-extrabold text-slate-900">{fmtMoney(totals.total)}</div>
                    {(totals.discount_amount > 0) && (
                        <div className="mt-1 text-xs text-slate-500">Discount applied: -{fmtMoney(totals.discount_amount)}</div>
                    )}
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Paid</div>
                    <div className="mt-1 text-3xl font-extrabold text-emerald-600">{fmtMoney(paid)}</div>
                    <div className="mt-1 text-xs text-slate-500">{(doc.payments||[]).length} payment(s)</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">Balance due</div>
                    <div className="mt-1 text-3xl font-extrabold text-[#DC2626]">{fmtMoney(balance)}</div>
                    {totals.deposit_amount > 0 && paid <= 0 && (
                        <div className="mt-1 text-xs text-slate-500">Deposit required: {fmtMoney(totals.deposit_amount)}</div>
                    )}
                </div>
            </div>

            {/* Charge actions */}
            {balance > 0 && (
                <div className="rounded-2xl border-2 border-[#1D4ED8]/20 bg-blue-50/30 p-5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                            <h3 className="font-bold text-slate-900 flex items-center gap-2"><CreditCard size={18}/> Take payment now</h3>
                            <p className="text-sm text-slate-600">Process a card payment for this customer.</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {totals.deposit_amount > 0 && paid <= 0 && (
                                <button onClick={() => checkout("deposit")}
                                    className="px-4 py-2.5 rounded-lg bg-white border-2 border-emerald-300 hover:bg-emerald-50 text-emerald-800 font-bold text-sm inline-flex items-center gap-2"
                                    data-testid="charge-deposit-button">
                                    <Coins size={16}/> Charge deposit ({fmtMoney(totals.deposit_amount)})
                                </button>
                            )}
                            <button onClick={() => checkout("balance")}
                                className="px-4 py-2.5 rounded-lg bg-[#DC2626] hover:bg-[#B91C1C] text-white font-bold text-sm inline-flex items-center gap-2"
                                data-testid="charge-balance-button">
                                <CreditCard size={16}/> Charge balance ({fmtMoney(balance)})
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Line items */}
            <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                <div className="px-5 py-3 bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                    Line items
                </div>
                <table className="w-full text-sm">
                    <thead className="text-xs uppercase tracking-wider text-slate-500">
                        <tr>
                            <th className="text-left px-5 py-2">Description</th>
                            <th className="text-right px-3 py-2">Qty</th>
                            <th className="text-right px-3 py-2">Price</th>
                            <th className="text-right px-5 py-2">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(doc.line_items||[]).map((li, i) => (
                            <tr key={i} className="border-t border-slate-100">
                                <td className="px-5 py-3">{li.description}</td>
                                <td className="px-3 py-3 text-right text-slate-500">{li.qty}</td>
                                <td className="px-3 py-3 text-right text-slate-500">{fmtMoney(li.unit_price)}</td>
                                <td className="px-5 py-3 text-right font-semibold">{fmtMoney((li.qty||0)*(li.unit_price||0))}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Payments history */}
            {(doc.payments||[]).length > 0 && (
                <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                    <div className="px-5 py-3 bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                        Payment history
                    </div>
                    <table className="w-full text-sm">
                        <tbody>
                            {doc.payments.map((p) => (
                                <tr key={p.id} className="border-t border-slate-100">
                                    <td className="px-5 py-3">
                                        <CheckCircle size={16} weight="fill" className="text-emerald-500 inline-block mr-1"/>
                                        <span className="font-semibold">{fmtMoney(p.amount)}</span>
                                        <span className="ml-2 text-xs text-slate-500 uppercase">{p.pay_type}</span>
                                    </td>
                                    <td className="px-5 py-3 text-right text-xs text-slate-500">
                                        {new Date(p.paid_at).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
