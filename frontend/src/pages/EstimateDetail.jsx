import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import api, { formatApiError, API_BASE } from "../lib/api";
import { toast } from "sonner";
import {
    ArrowLeft, PaperPlaneTilt, FilePdf, PencilSimple,
    Receipt, Link as LinkIcon, CheckCircle, ChatCircleText, Clock,
} from "@phosphor-icons/react";

const STATUS_META = {
    draft:     { label: "Draft",     cls: "bg-slate-100 text-slate-700 border-slate-300" },
    sent:      { label: "Sent",      cls: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30" },
    viewed:    { label: "Viewed",    cls: "bg-indigo-50 text-indigo-700 border-indigo-300" },
    approved:  { label: "Approved",  cls: "bg-emerald-50 text-emerald-700 border-emerald-400" },
    declined:  { label: "Declined",  cls: "bg-red-50 text-[#DC2626] border-[#DC2626]/40" },
    expired:   { label: "Expired",   cls: "bg-amber-50 text-amber-700 border-amber-400" },
    converted: { label: "Converted", cls: "bg-violet-50 text-violet-700 border-violet-300" },
};
const TIER_COLORS = {
    good:   "border-slate-300",
    better: "border-blue-400",
    best:   "border-amber-400",
};

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }

export default function EstimateDetail() {
    const navigate = useNavigate();
    const { id } = useParams();
    const [doc, setDoc] = useState(null);
    const [loading, setLoading] = useState(true);
    const [sending, setSending] = useState(false);

    const load = () => {
        api.get(`/estimates/${id}`).then((r) => setDoc(r.data))
            .catch((e) => toast.error(formatApiError(e.response?.data?.detail)))
            .finally(() => setLoading(false));
    };
    useEffect(() => { load(); }, [id]);

    const send = async () => {
        setSending(true);
        try {
            const r = await api.post(`/estimates/${id}/send`);
            toast.success("Proposal sent");
            if (r.data.link) {
                await navigator.clipboard?.writeText(r.data.link).catch(()=>{});
                toast.message("Link copied", { description: r.data.link });
            }
            load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setSending(false); }
    };

    const convert = async () => {
        try {
            const r = await api.post(`/estimates/${id}/convert`);
            toast.success(`Invoice ${r.data.number} created`);
            navigate(`/app/invoices/${r.data.id}`);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const copyLink = async () => {
        if (!doc?.public_token) return;
        const link = `${window.location.origin}/proposal/${doc.public_token}`;
        await navigator.clipboard.writeText(link);
        toast.success("Customer link copied");
    };

    if (loading) return <div className="text-sm text-slate-500">Loading…</div>;
    if (!doc) return null;

    const meta = STATUS_META[doc.status] || STATUS_META.draft;
    const totals = doc.totals_by_tier || {};
    const tiers = doc.tiers || [];
    const selectedTotals = doc.selected_tier ? totals[doc.selected_tier] : null;
    const canEdit = !["approved","converted","declined"].includes(doc.status);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                    <button onClick={() => navigate("/app/estimates")}
                        className="p-2 -ml-2 text-slate-600 hover:text-slate-900">
                        <ArrowLeft size={20} />
                    </button>
                    <div>
                        <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-bold text-slate-500">{doc.number}</span>
                            <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${meta.cls}`}>
                                {meta.label}
                            </span>
                        </div>
                        <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-900">{doc.title}</h1>
                        <div className="text-sm text-slate-500">
                            For <b>{doc.customer_name || "—"}</b> · {doc.customer_email || ""}
                        </div>
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    {canEdit && (
                        <button onClick={() => navigate(`/app/estimates/${id}/edit`)}
                            className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-3 py-2 rounded-lg font-semibold text-sm text-slate-700"
                            data-testid="edit-estimate-button">
                            <PencilSimple size={16} /> Edit
                        </button>
                    )}
                    <a href={`${API_BASE}/estimates/${id}/pdf`} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-3 py-2 rounded-lg font-semibold text-sm text-slate-700">
                        <FilePdf size={16} /> PDF
                    </a>
                    {doc.public_token && (
                        <button onClick={copyLink}
                            className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-3 py-2 rounded-lg font-semibold text-sm text-slate-700"
                            data-testid="copy-link-button">
                            <LinkIcon size={16} /> Copy link
                        </button>
                    )}
                    {canEdit && (
                        <button onClick={send} disabled={sending || !doc.customer_email}
                            className="inline-flex items-center gap-2 bg-[#1D4ED8] hover:bg-[#1E40AF] text-white px-3 py-2 rounded-lg font-semibold text-sm shadow-sm"
                            data-testid="send-estimate-button"
                            title={!doc.customer_email ? "Add a customer email first" : "Send proposal"}>
                            <PaperPlaneTilt size={16} weight="fill" /> Send
                        </button>
                    )}
                    {doc.status === "approved" && (
                        <button onClick={convert}
                            className="inline-flex items-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white px-3 py-2 rounded-lg font-semibold text-sm shadow-sm"
                            data-testid="convert-to-invoice-button">
                            <Receipt size={16} weight="fill" /> Convert to invoice
                        </button>
                    )}
                </div>
            </div>

            {/* Approved banner */}
            {doc.status === "approved" && doc.signature && (
                <div className="rounded-2xl border-2 border-emerald-400 bg-emerald-50/50 p-5">
                    <div className="flex items-start gap-3">
                        <CheckCircle size={28} weight="fill" className="text-emerald-600 shrink-0" />
                        <div className="flex-1">
                            <div className="font-bold text-emerald-900">Approved by {doc.signature.signer_name}</div>
                            <div className="text-sm text-emerald-800">
                                Signed on {new Date(doc.signature.signed_at).toLocaleString()} ·
                                Selected <b className="uppercase">{doc.selected_tier}</b> tier · Total {fmtMoney(selectedTotals?.total)}
                            </div>
                        </div>
                        {doc.signature.data_url && (
                            <img src={doc.signature.data_url} alt="Signature"
                                className="h-14 bg-white rounded border border-emerald-200" />
                        )}
                    </div>
                </div>
            )}

            {/* Tiers display (read-only) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {tiers.map((t) => {
                    const tt = totals[t.key] || {};
                    const monthly = doc.monthly_payment_by_tier?.[t.key];
                    const isSelected = doc.selected_tier === t.key;
                    return (
                        <div key={t.key}
                            className={`relative rounded-2xl bg-white border-2 ${isSelected ? "border-emerald-400" : TIER_COLORS[t.key]} p-5`}>
                            {t.featured && (
                                <div className="absolute -top-2 right-4 bg-amber-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded">
                                    Recommended
                                </div>
                            )}
                            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{t.key}</div>
                            <div className="text-2xl font-extrabold mt-1">{t.name}</div>
                            {t.summary && <div className="text-sm text-slate-500 mt-1">{t.summary}</div>}
                            <ul className="mt-4 space-y-1.5 text-sm">
                                {(t.line_items||[]).map((li, i) => (
                                    <li key={i} className="flex justify-between">
                                        <span className="text-slate-700">{li.description} {li.qty !== 1 && <span className="text-slate-400">× {li.qty}</span>}</span>
                                        <span className="text-slate-500">{fmtMoney(li.qty * li.unit_price)}</span>
                                    </li>
                                ))}
                            </ul>
                            {(t.addons||[]).length > 0 && (
                                <div className="mt-3 pt-3 border-t border-slate-100">
                                    <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Add-ons</div>
                                    <ul className="space-y-1 text-sm">
                                        {t.addons.map((a, i) => (
                                            <li key={i} className="flex justify-between">
                                                <span className="text-slate-600">+ {a.description}</span>
                                                <span className="text-slate-500">{fmtMoney(a.qty * a.unit_price)}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            <div className="mt-4 pt-3 border-t border-slate-200">
                                <div className="text-xs uppercase tracking-wider text-slate-500">Total</div>
                                <div className="text-3xl font-extrabold">{fmtMoney(tt.total)}</div>
                                {monthly > 0 && (
                                    <div className="mt-1 text-xs text-emerald-700 font-semibold">
                                        or {fmtMoney(monthly)}/mo financing
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Meta */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1">
                        <Clock size={12}/> Expires
                    </div>
                    <div className="mt-0.5 text-slate-700">{doc.expires_at ? new Date(doc.expires_at).toLocaleDateString() : "—"}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Sent</div>
                    <div className="mt-0.5 text-slate-700">{doc.sent_at ? new Date(doc.sent_at).toLocaleString() : "—"}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Viewed</div>
                    <div className="mt-0.5 text-slate-700">{doc.viewed_at ? new Date(doc.viewed_at).toLocaleString() : "—"}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Approved</div>
                    <div className="mt-0.5 text-slate-700">{doc.approved_at ? new Date(doc.approved_at).toLocaleString() : "—"}</div>
                </div>
            </div>

            {doc.converted_invoice_id && (
                <Link to={`/app/invoices/${doc.converted_invoice_id}`}
                    className="block rounded-2xl border border-violet-300 bg-violet-50/50 p-4 hover:bg-violet-50">
                    <div className="text-xs font-bold uppercase tracking-widest text-violet-700">Linked invoice</div>
                    <div className="mt-1 font-semibold text-violet-900">View invoice →</div>
                </Link>
            )}
        </div>
    );
}
