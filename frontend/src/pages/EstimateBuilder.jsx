import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash, Star, FloppyDisk, ArrowLeft, Sparkle, CreditCard } from "@phosphor-icons/react";
import { AIGenerateEstimateButton } from "../components/AIAssist";

const TIER_KEYS = ["good", "better", "best"];
const TIER_COLORS = {
    good:   { ring: "ring-slate-300", bar: "bg-slate-500",   badge: "bg-slate-100 text-slate-700" },
    better: { ring: "ring-blue-400",  bar: "bg-[#1D4ED8]",   badge: "bg-blue-50 text-[#1D4ED8]" },
    best:   { ring: "ring-amber-400", bar: "bg-amber-500",   badge: "bg-amber-50 text-amber-800" },
};

function emptyTier(key) {
    return {
        key,
        name: key[0].toUpperCase() + key.slice(1),
        summary: "",
        line_items: [],
        addons: [],
        featured: key === "better",
        cta_label: "Approve this option",
    };
}

function emptyEstimate() {
    return {
        title: "",
        intro: "",
        customer_name: "",
        customer_email: "",
        customer_phone: "",
        address: "",
        tax_rate: 0,
        discount: { type: "percent", value: 0 },
        deposit: { type: "none", value: 0 },
        financing: { enabled: false, apr: 9.99, term_months: 24, apply_url: "", provider: "wisetack" },
        terms: "By approving this proposal you agree to the scope of work described above. Final pricing may vary based on unforeseen conditions discovered during the work.",
        expires_in_days: 30,
        tiers: TIER_KEYS.map(emptyTier),
    };
}

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }

export default function EstimateBuilder() {
    const navigate = useNavigate();
    const { id } = useParams();
    const isEdit = !!id;
    const [form, setForm] = useState(emptyEstimate());
    const [saving, setSaving] = useState(false);
    const [loading, setLoading] = useState(isEdit);
    const [doc, setDoc] = useState(null); // server doc (for totals)
    const [templates, setTemplates] = useState([]);

    useEffect(() => {
        api.get("/templates", { params: { kind: "estimate" } }).then((r) => setTemplates(r.data || []));
        if (isEdit) {
            api.get(`/estimates/${id}`).then((r) => {
                const e = r.data;
                setDoc(e);
                setForm({
                    title: e.title, intro: e.intro || "",
                    customer_name: e.customer_name || "", customer_email: e.customer_email || "",
                    customer_phone: e.customer_phone || "", address: e.address || "",
                    tax_rate: e.tax_rate || 0,
                    discount: e.discount || { type: "percent", value: 0 },
                    deposit: e.deposit || { type: "none", value: 0 },
                    financing: e.financing || { enabled: false, apr: 9.99, term_months: 24, apply_url: "" },
                    terms: e.terms || "",
                    expires_in_days: 30,
                    tiers: TIER_KEYS.map((k) =>
                        (e.tiers || []).find((t) => t.key === k) || emptyTier(k)
                    ),
                });
            }).catch((err) => toast.error(formatApiError(err.response?.data?.detail)))
            .finally(() => setLoading(false));
        }
    }, [id, isEdit]);

    // Local totals calc that matches backend math
    const computeTier = (tier) => {
        const allItems = [...(tier.line_items||[]), ...(tier.addons||[]).filter(a=>a.selected)];
        const subtotal = allItems.reduce((s,i) => s + (Number(i.qty)||0) * (Number(i.unit_price)||0), 0);
        const taxable = allItems.filter(i=>i.taxable!==false)
            .reduce((s,i) => s + (Number(i.qty)||0) * (Number(i.unit_price)||0), 0);
        const dval = Number(form.discount?.value)||0;
        const discountAmount = form.discount?.type === "percent"
            ? subtotal * dval / 100
            : Math.min(dval, subtotal);
        const ratio = subtotal > 0 ? (subtotal - discountAmount)/subtotal : 1;
        const taxableAfter = taxable * ratio;
        const taxAmount = taxableAfter * (Number(form.tax_rate)||0)/100;
        const total = subtotal - discountAmount + taxAmount;
        const depVal = Number(form.deposit?.value)||0;
        const depAmount = form.deposit?.type === "percent"
            ? total * depVal/100
            : form.deposit?.type === "fixed" ? Math.min(depVal, total) : 0;
        return { subtotal, discountAmount, taxAmount, total, depAmount };
    };

    const monthlyPayment = (principal) => {
        const apr = Number(form.financing?.apr)||0;
        const n = Number(form.financing?.term_months)||0;
        if (principal <= 0 || n <= 0) return 0;
        const r = (apr/100)/12;
        if (r <= 0) return principal/n;
        return principal * (r * Math.pow(1+r, n)) / (Math.pow(1+r, n) - 1);
    };

    const updateTier = (idx, patch) => {
        setForm((f) => ({
            ...f,
            tiers: f.tiers.map((t,i) => i===idx ? {...t, ...patch} : t),
        }));
    };

    const updateLineItem = (tierIdx, list, itemIdx, patch) => {
        setForm((f) => ({
            ...f,
            tiers: f.tiers.map((t,i) => {
                if (i !== tierIdx) return t;
                const arr = [...(t[list] || [])];
                arr[itemIdx] = { ...arr[itemIdx], ...patch };
                return { ...t, [list]: arr };
            }),
        }));
    };

    const addLineItem = (tierIdx, list) => {
        setForm((f) => ({
            ...f,
            tiers: f.tiers.map((t,i) => i!==tierIdx ? t : {
                ...t,
                [list]: [...(t[list]||[]), {
                    description: "", qty: 1, unit_price: 0,
                    taxable: true, kind: list === "addons" ? "material" : "service",
                    selected: list === "addons" ? false : undefined,
                }],
            }),
        }));
    };

    const removeLineItem = (tierIdx, list, itemIdx) => {
        setForm((f) => ({
            ...f,
            tiers: f.tiers.map((t,i) => i!==tierIdx ? t : {
                ...t, [list]: (t[list]||[]).filter((_,j) => j !== itemIdx),
            }),
        }));
    };

    const applyTemplate = (tpl) => {
        if (!tpl || !tpl.tiers) return;
        setForm((f) => ({
            ...f,
            tax_rate: tpl.tax_rate || f.tax_rate,
            terms: tpl.terms || f.terms,
            tiers: TIER_KEYS.map((k) =>
                (tpl.tiers || []).find((t) => t.key === k) || emptyTier(k)
            ),
        }));
        toast.success(`Template "${tpl.name}" applied`);
    };

    const save = async (also) => {
        if (!form.title.trim()) return toast.error("Please add a title");
        setSaving(true);
        try {
            const body = {
                ...form,
                tax_rate: Number(form.tax_rate)||0,
                discount: { type: form.discount.type, value: Number(form.discount.value)||0 },
                deposit: { type: form.deposit.type, value: Number(form.deposit.value)||0 },
                financing: { ...form.financing,
                    apr: Number(form.financing.apr)||0,
                    term_months: Number(form.financing.term_months)||0,
                },
                expires_in_days: Number(form.expires_in_days)||30,
            };
            const r = isEdit
                ? await api.put(`/estimates/${id}`, body)
                : await api.post("/estimates", body);
            toast.success(isEdit ? "Estimate updated" : "Estimate created");
            if (also === "send") {
                await api.post(`/estimates/${r.data.id}/send`);
                toast.success("Proposal emailed to customer");
            }
            navigate(`/app/estimates/${r.data.id}`);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setSaving(false); }
    };

    if (loading) return <div className="text-sm text-slate-500">Loading…</div>;

    return (
        <div className="space-y-6 pb-20">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => navigate("/app/estimates")}
                        className="p-2 -ml-2 text-slate-600 hover:text-slate-900"
                        data-testid="back-to-estimates"
                    ><ArrowLeft size={20} /></button>
                    <div>
                        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
                            {isEdit ? `Edit Estimate ${doc?.number||""}` : "New Estimate"}
                        </h1>
                        <p className="text-sm text-slate-500">Build a Good / Better / Best proposal with financing.</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <AIGenerateEstimateButton onGenerated={(g) => {
                        setForm((f) => ({
                            ...f,
                            title: g.title || f.title,
                            intro: g.intro || f.intro,
                            tiers: TIER_KEYS.map((k) =>
                                (g.tiers || []).find((t) => t.key === k) || emptyTier(k)
                            ),
                        }));
                    }} />
                    {templates.length > 0 && (
                        <select
                            className="text-sm border border-slate-200 rounded-lg px-3 py-2"
                            onChange={(e) => {
                                const tpl = templates.find((t)=>t.id===e.target.value);
                                if (tpl) applyTemplate(tpl);
                                e.target.value = "";
                            }}
                            data-testid="template-select"
                            defaultValue=""
                        >
                            <option value="" disabled>Apply template…</option>
                            {templates.map((t) => (
                                <option key={t.id} value={t.id}>{t.name}</option>
                            ))}
                        </select>
                    )}
                    <button
                        onClick={() => save("draft")}
                        disabled={saving}
                        className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-4 py-2.5 rounded-lg font-semibold text-slate-700"
                        data-testid="save-estimate-button"
                    >
                        <FloppyDisk size={18} /> Save Draft
                    </button>
                    <button
                        onClick={() => save("send")}
                        disabled={saving}
                        className="inline-flex items-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white px-4 py-2.5 rounded-lg font-semibold shadow-sm"
                        data-testid="save-send-estimate-button"
                    >
                        <Sparkle size={18} weight="fill" /> Save & Send
                    </button>
                </div>
            </div>

            {/* Customer + meta */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Proposal title</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg" placeholder="e.g. HVAC System Replacement"
                            value={form.title} onChange={(e) => setForm({...form, title: e.target.value})}
                            data-testid="estimate-title-input" />
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer name</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.customer_name} onChange={(e) => setForm({...form, customer_name: e.target.value})}
                            data-testid="customer-name-input" />
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer email</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg" type="email"
                            value={form.customer_email} onChange={(e) => setForm({...form, customer_email: e.target.value})}
                            data-testid="customer-email-input" />
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer phone</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.customer_phone} onChange={(e) => setForm({...form, customer_phone: e.target.value})} />
                    </div>
                    <div className="sm:col-span-2">
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Service address</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.address} onChange={(e) => setForm({...form, address: e.target.value})} />
                    </div>
                    <div className="sm:col-span-2">
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Intro / scope summary</label>
                        <textarea className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg" rows={2}
                            value={form.intro} onChange={(e) => setForm({...form, intro: e.target.value})}
                            placeholder="A short overview the customer will see at the top of the proposal…" />
                    </div>
                </div>
            </div>

            {/* Tier columns */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {form.tiers.map((tier, idx) => {
                    const totals = computeTier(tier);
                    const monthly = form.financing.enabled ? monthlyPayment(totals.total) : 0;
                    const color = TIER_COLORS[tier.key];
                    return (
                        <div key={tier.key} className={`relative rounded-2xl bg-white border border-slate-200 overflow-hidden ring-2 ${color.ring} transition`}>
                            {tier.featured && (
                                <div className="absolute top-0 right-0 m-3 inline-flex items-center gap-1 bg-amber-500 text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full">
                                    <Star size={10} weight="fill" /> Recommended
                                </div>
                            )}
                            <div className={`${color.bar} h-1.5 w-full`} />
                            <div className="p-5 space-y-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <div className={`inline-block text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded ${color.badge}`}>
                                            Tier
                                        </div>
                                        <input
                                            className="block mt-1 text-2xl font-extrabold tracking-tight bg-transparent w-full focus:outline-none"
                                            value={tier.name}
                                            onChange={(e) => updateTier(idx, { name: e.target.value })}
                                            data-testid={`tier-name-${tier.key}`}
                                        />
                                    </div>
                                    <label className="inline-flex items-center gap-1 text-xs text-slate-500 cursor-pointer">
                                        <input type="checkbox" checked={!!tier.featured}
                                            onChange={(e) => {
                                                // only one featured at a time
                                                setForm((f) => ({ ...f, tiers: f.tiers.map((t,i)=>({...t, featured: i===idx ? e.target.checked : false}))}));
                                            }} />
                                        Featured
                                    </label>
                                </div>
                                <input
                                    className="w-full text-sm px-3 py-2 border border-slate-200 rounded-lg"
                                    placeholder="One-line summary the customer sees"
                                    value={tier.summary || ""}
                                    onChange={(e) => updateTier(idx, { summary: e.target.value })}
                                />

                                {/* Line items */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Line items</div>
                                        <button onClick={() => addLineItem(idx, "line_items")}
                                            className="text-xs font-semibold text-[#1D4ED8] hover:underline inline-flex items-center gap-1"
                                            data-testid={`add-line-${tier.key}`}>
                                            <Plus size={12} weight="bold" /> Add
                                        </button>
                                    </div>
                                    {(tier.line_items||[]).map((li, li_idx) => (
                                        <div key={li_idx} className="bg-slate-50 p-2.5 rounded-lg space-y-1.5">
                                            <input className="w-full text-sm px-2 py-1 border border-slate-200 rounded bg-white"
                                                placeholder="Description"
                                                value={li.description||""}
                                                onChange={(e) => updateLineItem(idx, "line_items", li_idx, { description: e.target.value })} />
                                            <div className="grid grid-cols-12 gap-1.5 items-center">
                                                <input type="number" step="0.5" min="0" className="col-span-3 text-sm px-2 py-1 border border-slate-200 rounded bg-white"
                                                    value={li.qty}
                                                    onChange={(e) => updateLineItem(idx, "line_items", li_idx, { qty: parseFloat(e.target.value)||0 })} />
                                                <input type="number" step="0.01" min="0" className="col-span-4 text-sm px-2 py-1 border border-slate-200 rounded bg-white"
                                                    value={li.unit_price}
                                                    onChange={(e) => updateLineItem(idx, "line_items", li_idx, { unit_price: parseFloat(e.target.value)||0 })} />
                                                <label className="col-span-3 inline-flex items-center gap-1 text-xs text-slate-600">
                                                    <input type="checkbox" checked={li.taxable!==false}
                                                        onChange={(e) => updateLineItem(idx, "line_items", li_idx, { taxable: e.target.checked })} />
                                                    Tax
                                                </label>
                                                <button onClick={() => removeLineItem(idx, "line_items", li_idx)}
                                                    className="col-span-2 text-slate-400 hover:text-[#DC2626] justify-self-end">
                                                    <Trash size={16} />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Addons (optional) */}
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Optional add-ons</div>
                                        <button onClick={() => addLineItem(idx, "addons")}
                                            className="text-xs font-semibold text-[#1D4ED8] hover:underline inline-flex items-center gap-1">
                                            <Plus size={12} weight="bold" /> Add
                                        </button>
                                    </div>
                                    {(tier.addons||[]).map((a, a_idx) => (
                                        <div key={a_idx} className="bg-amber-50/50 p-2.5 rounded-lg space-y-1.5">
                                            <input className="w-full text-sm px-2 py-1 border border-slate-200 rounded bg-white"
                                                placeholder="Add-on description"
                                                value={a.description||""}
                                                onChange={(e) => updateLineItem(idx, "addons", a_idx, { description: e.target.value })} />
                                            <div className="grid grid-cols-12 gap-1.5 items-center">
                                                <input type="number" step="0.5" min="0" className="col-span-3 text-sm px-2 py-1 border border-slate-200 rounded bg-white"
                                                    value={a.qty}
                                                    onChange={(e) => updateLineItem(idx, "addons", a_idx, { qty: parseFloat(e.target.value)||0 })} />
                                                <input type="number" step="0.01" min="0" className="col-span-4 text-sm px-2 py-1 border border-slate-200 rounded bg-white"
                                                    value={a.unit_price}
                                                    onChange={(e) => updateLineItem(idx, "addons", a_idx, { unit_price: parseFloat(e.target.value)||0 })} />
                                                <label className="col-span-3 inline-flex items-center gap-1 text-xs text-slate-600">
                                                    <input type="checkbox" checked={a.taxable!==false}
                                                        onChange={(e) => updateLineItem(idx, "addons", a_idx, { taxable: e.target.checked })} />
                                                    Tax
                                                </label>
                                                <button onClick={() => removeLineItem(idx, "addons", a_idx)}
                                                    className="col-span-2 text-slate-400 hover:text-[#DC2626] justify-self-end">
                                                    <Trash size={16} />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Tier totals preview */}
                                <div className="pt-2 border-t border-slate-100 space-y-0.5 text-sm">
                                    <div className="flex justify-between text-slate-500">
                                        <span>Subtotal</span><span>{fmtMoney(totals.subtotal)}</span>
                                    </div>
                                    {totals.discountAmount > 0 && (
                                        <div className="flex justify-between text-slate-500">
                                            <span>Discount</span><span>-{fmtMoney(totals.discountAmount)}</span>
                                        </div>
                                    )}
                                    {totals.taxAmount > 0 && (
                                        <div className="flex justify-between text-slate-500">
                                            <span>Tax</span><span>{fmtMoney(totals.taxAmount)}</span>
                                        </div>
                                    )}
                                    <div className="flex justify-between items-baseline pt-1">
                                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total</span>
                                        <span className="text-2xl font-extrabold text-slate-900">{fmtMoney(totals.total)}</span>
                                    </div>
                                    {form.financing.enabled && totals.total > 0 && (
                                        <div className="mt-2 rounded-lg bg-emerald-50 border border-emerald-200 p-2 text-xs text-emerald-800">
                                            or <b>{fmtMoney(monthly)}/mo</b> for {form.financing.term_months} months · {form.financing.apr}% APR
                                        </div>
                                    )}
                                    {totals.depAmount > 0 && (
                                        <div className="mt-1 text-xs text-slate-500">Deposit: {fmtMoney(totals.depAmount)}</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Settings */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
                    <h3 className="font-bold text-slate-900">Tax, Discount & Deposit</h3>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tax rate (%)</label>
                            <input type="number" step="0.01" className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                value={form.tax_rate}
                                onChange={(e) => setForm({...form, tax_rate: parseFloat(e.target.value)||0})} />
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Discount</label>
                            <div className="flex gap-1.5 mt-1">
                                <select className="px-2 py-2 border border-slate-200 rounded-lg text-sm"
                                    value={form.discount.type}
                                    onChange={(e) => setForm({...form, discount: {...form.discount, type: e.target.value}})}>
                                    <option value="percent">%</option>
                                    <option value="fixed">$</option>
                                </select>
                                <input type="number" step="0.01" className="flex-1 px-3 py-2 border border-slate-200 rounded-lg"
                                    value={form.discount.value}
                                    onChange={(e) => setForm({...form, discount: {...form.discount, value: parseFloat(e.target.value)||0}})} />
                            </div>
                        </div>
                        <div className="col-span-2">
                            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Deposit required</label>
                            <div className="flex gap-1.5 mt-1">
                                <select className="px-2 py-2 border border-slate-200 rounded-lg text-sm"
                                    value={form.deposit.type}
                                    onChange={(e) => setForm({...form, deposit: {...form.deposit, type: e.target.value}})}>
                                    <option value="none">No deposit</option>
                                    <option value="percent">% of total</option>
                                    <option value="fixed">Fixed $</option>
                                </select>
                                {form.deposit.type !== "none" && (
                                    <input type="number" step="0.01" className="flex-1 px-3 py-2 border border-slate-200 rounded-lg"
                                        value={form.deposit.value}
                                        onChange={(e) => setForm({...form, deposit: {...form.deposit, value: parseFloat(e.target.value)||0}})} />
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
                    <div className="flex items-center justify-between">
                        <h3 className="font-bold text-slate-900 flex items-center gap-2"><CreditCard size={18}/> Financing</h3>
                        <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
                            <input type="checkbox" checked={form.financing.enabled}
                                onChange={(e) => setForm({...form, financing: {...form.financing, enabled: e.target.checked}})}
                                data-testid="financing-enabled-toggle" />
                            <span>{form.financing.enabled ? "On" : "Off"}</span>
                        </label>
                    </div>
                    {form.financing.enabled && (
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">APR (%)</label>
                                <input type="number" step="0.01" className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                    value={form.financing.apr}
                                    onChange={(e) => setForm({...form, financing: {...form.financing, apr: parseFloat(e.target.value)||0}})} />
                            </div>
                            <div>
                                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Term (months)</label>
                                <input type="number" className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                    value={form.financing.term_months}
                                    onChange={(e) => setForm({...form, financing: {...form.financing, term_months: parseInt(e.target.value)||0}})} />
                            </div>
                            <div className="col-span-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Apply URL (optional)</label>
                                <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                    placeholder="https://apply.wisetack.com/..."
                                    value={form.financing.apply_url||""}
                                    onChange={(e) => setForm({...form, financing: {...form.financing, apply_url: e.target.value}})} />
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Terms */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <h3 className="font-bold text-slate-900">Terms & expiration</h3>
                <textarea className="mt-2 w-full px-3 py-2 border border-slate-200 rounded-lg" rows={3}
                    value={form.terms} onChange={(e) => setForm({...form, terms: e.target.value})} />
                <div className="mt-3 flex items-center gap-2">
                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Expires in (days)</label>
                    <input type="number" min="1" className="px-3 py-2 border border-slate-200 rounded-lg w-24"
                        value={form.expires_in_days}
                        onChange={(e) => setForm({...form, expires_in_days: parseInt(e.target.value)||30})} />
                </div>
            </div>
        </div>
    );
}
