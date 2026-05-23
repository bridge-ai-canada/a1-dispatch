import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast, Toaster } from "sonner";
import SignaturePad from "../components/SignaturePad";
import CustomerChatbot from "../components/CustomerChatbot";
import {
    CheckCircle, Star, ShieldCheck, FilePdf, CreditCard,
    SealCheck, X, ChatCircleText, Confetti,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TIER_ACCENT = {
    good:   { border: "border-slate-300", chip: "bg-slate-100 text-slate-700", btn: "bg-slate-800 hover:bg-slate-900" },
    better: { border: "border-blue-400",  chip: "bg-blue-50 text-[#1D4ED8]",   btn: "bg-[#1D4ED8] hover:bg-[#1E40AF]" },
    best:   { border: "border-amber-400", chip: "bg-amber-50 text-amber-800",  btn: "bg-amber-600 hover:bg-amber-700" },
};

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }

export default function PublicEstimate() {
    const { token } = useParams();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedTier, setSelectedTier] = useState(null);
    const [selectedAddons, setSelectedAddons] = useState({});
    const [showApprove, setShowApprove] = useState(false);
    const [showDecline, setShowDecline] = useState(false);
    const [signerName, setSignerName] = useState("");
    const [signatureData, setSignatureData] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [agreedToTerms, setAgreedToTerms] = useState(false);
    const [declineReason, setDeclineReason] = useState("");

    useEffect(() => {
        axios.get(`${API}/public/estimates/${token}`)
            .then((r) => {
                setData(r.data);
                const featured = (r.data.estimate.tiers || []).find((t) => t.featured);
                setSelectedTier(featured ? featured.key : "better");
            })
            .catch(() => toast.error("Proposal not found or expired"))
            .finally(() => setLoading(false));
    }, [token]);

    if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading proposal…</div>;
    if (!data) return <div className="min-h-screen flex items-center justify-center text-slate-500">Proposal not found.</div>;

    const { estimate, company } = data;
    const tiers = estimate.tiers || [];
    const totals = estimate.totals_by_tier || {};
    const monthly = estimate.monthly_payment_by_tier || {};

    // Re-compute totals when addons toggled
    const computeWithAddons = (tier) => {
        const addonItems = (tier.addons || []).filter((a) => selectedAddons[a.id]);
        const subtotal = [...(tier.line_items||[]), ...addonItems]
            .reduce((s,i) => s + (Number(i.qty)||0) * (Number(i.unit_price)||0), 0);
        const taxable = [...(tier.line_items||[]), ...addonItems]
            .filter((i) => i.taxable !== false)
            .reduce((s,i) => s + (Number(i.qty)||0) * (Number(i.unit_price)||0), 0);
        const dval = Number(estimate.discount?.value)||0;
        const discountAmount = estimate.discount?.type === "percent"
            ? subtotal * dval/100 : Math.min(dval, subtotal);
        const ratio = subtotal > 0 ? (subtotal - discountAmount)/subtotal : 1;
        const taxAmount = (taxable * ratio) * (Number(estimate.tax_rate)||0)/100;
        const total = subtotal - discountAmount + taxAmount;
        const depVal = Number(estimate.deposit?.value)||0;
        const depAmount = estimate.deposit?.type === "percent" ? total * depVal/100
            : estimate.deposit?.type === "fixed" ? Math.min(depVal, total) : 0;
        // monthly
        const apr = Number(estimate.financing?.apr)||0;
        const n = Number(estimate.financing?.term_months)||0;
        const r = (apr/100)/12;
        const mp = total <= 0 || n <= 0 ? 0
            : (r <= 0 ? total/n : total * (r * Math.pow(1+r, n))/(Math.pow(1+r,n)-1));
        return { subtotal, discountAmount, taxAmount, total, depAmount, monthly: mp };
    };

    const tierLive = tiers.reduce((acc, t) => { acc[t.key] = computeWithAddons(t); return acc; }, {});

    const approve = async () => {
        if (!signerName.trim()) return toast.error("Please type your full name");
        if (!signatureData) return toast.error("Please draw your signature");
        if (!agreedToTerms) return toast.error("Please agree to the terms");
        setSubmitting(true);
        try {
            const selectedAddonIds = Object.entries(selectedAddons).filter(([_,v])=>v).map(([k])=>k);
            const r = await axios.post(`${API}/public/estimates/${token}/approve`, {
                selected_tier: selectedTier,
                signer_name: signerName.trim(),
                signature_base64: signatureData,
                selected_addons: selectedAddonIds,
            });
            setData((d) => ({ ...d, estimate: r.data }));
            setShowApprove(false);
            toast.success("Approved! Your contractor has been notified.");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Approval failed");
        } finally { setSubmitting(false); }
    };

    const decline = async () => {
        setSubmitting(true);
        try {
            await axios.post(`${API}/public/estimates/${token}/decline`, { reason: declineReason });
            const r = await axios.get(`${API}/public/estimates/${token}`);
            setData(r.data);
            setShowDecline(false);
            toast.message("Thanks for letting us know.");
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        } finally { setSubmitting(false); }
    };

    const approved = estimate.status === "approved" || estimate.status === "converted";
    const declined = estimate.status === "declined";

    const primary = company?.branding?.primary_color || "#1D4ED8";

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <Toaster position="top-center" richColors />
            {/* Top brand bar */}
            <header className="bg-white border-b border-slate-200">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
                    <div>
                        <div className="text-xs font-bold uppercase tracking-widest" style={{ color: primary }}>
                            {company?.industry || "Service Pro"}
                        </div>
                        <div className="text-xl font-extrabold tracking-tight">{company?.name || "A1 Field Pro"}</div>
                    </div>
                    <a href={`${API}/public/estimates/${token}/pdf`} target="_blank" rel="noreferrer"
                        className="hidden sm:inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900"
                        data-testid="download-pdf-button">
                        <FilePdf size={18}/> Download PDF
                    </a>
                </div>
            </header>

            {/* Hero */}
            <section className="bg-white border-b border-slate-100">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                        <div>
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-500">{estimate.number} · Your proposal</div>
                            <h1 className="mt-1 text-3xl sm:text-5xl font-extrabold tracking-tight">{estimate.title}</h1>
                            <p className="mt-2 text-slate-600">
                                Prepared for <b>{estimate.customer_name}</b>{estimate.address ? ` · ${estimate.address}` : ""}
                            </p>
                            {estimate.intro && (
                                <p className="mt-4 max-w-2xl text-slate-700 leading-relaxed">{estimate.intro}</p>
                            )}
                        </div>
                        <div className="flex flex-col items-end gap-2">
                            {approved && (
                                <div className="inline-flex items-center gap-2 bg-emerald-100 border border-emerald-300 text-emerald-800 px-3 py-1.5 rounded-full text-sm font-bold">
                                    <SealCheck size={18} weight="fill"/> Approved & Signed
                                </div>
                            )}
                            {declined && (
                                <div className="inline-flex items-center gap-2 bg-red-100 border border-red-300 text-[#DC2626] px-3 py-1.5 rounded-full text-sm font-bold">
                                    <X size={18} weight="bold"/> Declined
                                </div>
                            )}
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <ShieldCheck size={16}/> Secure proposal
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Tier comparison */}
            <section className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
                <div className="text-center mb-8">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Choose your package</div>
                    <h2 className="mt-2 text-2xl sm:text-3xl font-extrabold tracking-tight">
                        Pick the option that's right for you
                    </h2>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
                    {tiers.map((t) => {
                        const isSelected = selectedTier === t.key;
                        const live = tierLive[t.key] || {};
                        const accent = TIER_ACCENT[t.key] || TIER_ACCENT.better;
                        const locked = approved || declined;
                        return (
                            <div key={t.key}
                                onClick={() => !locked && setSelectedTier(t.key)}
                                className={`relative rounded-3xl bg-white border-2 p-6 transition cursor-pointer
                                    ${isSelected ? "border-[#1D4ED8] shadow-xl scale-[1.02]" : `${accent.border} hover:border-slate-400`}
                                    ${locked ? "cursor-default" : ""}`}
                                data-testid={`public-tier-${t.key}`}
                            >
                                {t.featured && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 bg-amber-500 text-white text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full shadow-md">
                                        <Star size={12} weight="fill"/> Most popular
                                    </div>
                                )}
                                {isSelected && !locked && (
                                    <div className="absolute top-4 right-4 text-[#1D4ED8]">
                                        <CheckCircle size={28} weight="fill"/>
                                    </div>
                                )}
                                <div className={`inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded ${accent.chip}`}>
                                    {t.key}
                                </div>
                                <div className="mt-2 text-3xl font-extrabold tracking-tight">{t.name}</div>
                                {t.summary && <div className="mt-1 text-sm text-slate-600">{t.summary}</div>}

                                {/* Price */}
                                <div className="mt-5 mb-4">
                                    <div className="text-4xl font-extrabold tracking-tight">{fmtMoney(live.total)}</div>
                                    {estimate.financing?.enabled && live.monthly > 0 && (
                                        <div className="mt-1 text-sm text-emerald-700 font-semibold">
                                            or <b>{fmtMoney(live.monthly)}/mo</b> · {estimate.financing.term_months} mo · {estimate.financing.apr}% APR
                                        </div>
                                    )}
                                    {live.depAmount > 0 && (
                                        <div className="mt-1 text-xs text-slate-500">Just {fmtMoney(live.depAmount)} due today</div>
                                    )}
                                </div>

                                {/* What's included */}
                                <ul className="space-y-2 text-sm">
                                    {(t.line_items||[]).map((li, i) => (
                                        <li key={i} className="flex items-start gap-2">
                                            <CheckCircle size={16} weight="fill" className="mt-0.5 text-emerald-500 shrink-0"/>
                                            <span className="text-slate-700">
                                                {li.description}
                                                {li.qty !== 1 && <span className="text-slate-400"> × {li.qty}</span>}
                                            </span>
                                        </li>
                                    ))}
                                </ul>

                                {/* Add-ons */}
                                {(t.addons||[]).length > 0 && (
                                    <div className="mt-5 pt-4 border-t border-slate-100">
                                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">
                                            Optional add-ons
                                        </div>
                                        <div className="space-y-2">
                                            {t.addons.map((a) => (
                                                <label key={a.id} onClick={(e)=>e.stopPropagation()}
                                                    className="flex items-start gap-2 p-2 rounded-lg hover:bg-slate-50 cursor-pointer">
                                                    <input type="checkbox"
                                                        disabled={locked}
                                                        checked={!!selectedAddons[a.id]}
                                                        onChange={(e) => setSelectedAddons({...selectedAddons, [a.id]: e.target.checked})}
                                                        className="mt-1"
                                                        data-testid={`addon-${a.id}`}/>
                                                    <div className="flex-1">
                                                        <div className="text-sm font-medium">{a.description}</div>
                                                        <div className="text-xs text-slate-500">+ {fmtMoney(a.qty * a.unit_price)}</div>
                                                    </div>
                                                </label>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* Apply / sticky CTA */}
            {!approved && !declined && (
                <section className="sticky bottom-0 bg-white border-t-2 border-slate-200 shadow-2xl">
                    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-3">
                        <div>
                            <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Your selection</div>
                            <div className="text-xl font-extrabold tracking-tight">
                                {tiers.find(t=>t.key===selectedTier)?.name} · {fmtMoney(tierLive[selectedTier]?.total)}
                            </div>
                            {tierLive[selectedTier]?.monthly > 0 && estimate.financing?.enabled && (
                                <div className="text-xs text-emerald-700 font-semibold">
                                    {fmtMoney(tierLive[selectedTier].monthly)}/mo with financing
                                </div>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <button onClick={() => setShowDecline(true)}
                                className="px-4 py-3 rounded-xl bg-white border border-slate-200 hover:border-slate-400 font-semibold text-sm text-slate-600"
                                data-testid="public-decline-button">
                                Not right now
                            </button>
                            {estimate.financing?.apply_url && (
                                <a href={estimate.financing.apply_url} target="_blank" rel="noreferrer"
                                    className="px-4 py-3 rounded-xl border-2 border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold text-sm inline-flex items-center gap-2">
                                    <CreditCard size={16}/> Apply for financing
                                </a>
                            )}
                            <button onClick={() => setShowApprove(true)}
                                className="px-6 py-3 rounded-xl bg-[#DC2626] hover:bg-[#B91C1C] text-white font-bold text-sm shadow-md inline-flex items-center gap-2"
                                data-testid="public-approve-button">
                                <SealCheck size={18} weight="fill"/> Approve & Sign
                            </button>
                        </div>
                    </div>
                </section>
            )}

            {/* Approval modal */}
            {showApprove && (
                <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-end sm:items-center justify-center p-2 sm:p-4">
                    <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl">
                        <div className="flex items-start justify-between">
                            <div>
                                <h3 className="text-2xl font-extrabold tracking-tight">Approve & sign</h3>
                                <p className="mt-1 text-sm text-slate-500">
                                    You're choosing <b className="capitalize">{tiers.find(t=>t.key===selectedTier)?.name}</b> for <b>{fmtMoney(tierLive[selectedTier]?.total)}</b>.
                                </p>
                            </div>
                            <button onClick={() => setShowApprove(false)} className="p-2 text-slate-400 hover:text-slate-700">
                                <X size={20}/>
                            </button>
                        </div>

                        <div className="mt-5 space-y-4">
                            <div>
                                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Type your full name</label>
                                <input className="mt-1 w-full px-4 py-3 border border-slate-200 rounded-xl text-lg font-semibold"
                                    placeholder="Jane Doe"
                                    value={signerName} onChange={(e) => setSignerName(e.target.value)}
                                    data-testid="signer-name-input"/>
                            </div>
                            <div>
                                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sign below</label>
                                <div className="mt-1">
                                    <SignaturePad onChange={setSignatureData}/>
                                </div>
                            </div>
                            <label className="flex items-start gap-2 text-sm text-slate-600">
                                <input type="checkbox" className="mt-1" checked={agreedToTerms}
                                    onChange={(e) => setAgreedToTerms(e.target.checked)}
                                    data-testid="agree-terms-checkbox"/>
                                <span>
                                    I agree to the <b>terms of this proposal</b> and authorize work to begin.
                                </span>
                            </label>
                            {estimate.terms && (
                                <details className="text-xs text-slate-500 bg-slate-50 rounded-lg p-3">
                                    <summary className="cursor-pointer font-semibold">Read full terms</summary>
                                    <p className="mt-2 whitespace-pre-wrap">{estimate.terms}</p>
                                </details>
                            )}
                            <button onClick={approve} disabled={submitting}
                                className="w-full inline-flex items-center justify-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-bold py-4 rounded-xl text-base shadow-lg disabled:opacity-50"
                                data-testid="submit-approval-button">
                                <SealCheck size={20} weight="fill"/>
                                {submitting ? "Submitting…" : "Approve & sign electronically"}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Decline modal */}
            {showDecline && (
                <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-end sm:items-center justify-center p-2 sm:p-4">
                    <div className="bg-white rounded-3xl max-w-md w-full p-6 sm:p-8 shadow-2xl">
                        <div className="flex items-start justify-between">
                            <h3 className="text-xl font-extrabold tracking-tight">Decline proposal</h3>
                            <button onClick={() => setShowDecline(false)} className="p-2 text-slate-400 hover:text-slate-700">
                                <X size={20}/>
                            </button>
                        </div>
                        <p className="mt-2 text-sm text-slate-600">Let us know what didn't work for you (optional).</p>
                        <textarea className="mt-3 w-full border border-slate-200 rounded-xl px-3 py-2" rows={3}
                            value={declineReason}
                            placeholder="Price is too high, need to think about it, etc."
                            onChange={(e) => setDeclineReason(e.target.value)}
                            data-testid="decline-reason-input"/>
                        <button onClick={decline} disabled={submitting}
                            className="mt-4 w-full bg-slate-900 text-white font-bold py-3 rounded-xl disabled:opacity-50"
                            data-testid="submit-decline-button">
                            {submitting ? "Submitting…" : "Submit"}
                        </button>
                    </div>
                </div>
            )}

            {/* Signed-receipt */}
            {approved && (
                <section className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
                    <div className="rounded-3xl border-2 border-emerald-300 bg-emerald-50/60 p-6 sm:p-8 text-center">
                        <Confetti size={48} className="mx-auto text-emerald-500" weight="fill"/>
                        <h3 className="mt-3 text-2xl font-extrabold tracking-tight">You're all set!</h3>
                        <p className="mt-1 text-slate-700">
                            Approved by <b>{estimate.signature?.signer_name}</b> on {new Date(estimate.signature?.signed_at).toLocaleString()}.
                        </p>
                        {estimate.signature?.data_url && (
                            <img src={estimate.signature.data_url} alt="Signature" className="mt-4 mx-auto h-20 bg-white rounded border border-emerald-200"/>
                        )}
                        <a href={`${API}/public/estimates/${token}/pdf`} target="_blank" rel="noreferrer"
                            className="mt-4 inline-flex items-center gap-2 bg-white border-2 border-slate-200 hover:border-slate-400 px-4 py-2 rounded-lg font-semibold text-sm">
                            <FilePdf size={16}/> Download signed copy
                        </a>
                    </div>
                </section>
            )}

            <footer className="text-center py-8 text-xs text-slate-400">
                Powered by A1 Field Pro · Secure proposal
            </footer>
            <CustomerChatbot companyId={company?.id || estimate?.company_id}
                companyName={company?.name} primary={primary}/>
        </div>
    );
}
