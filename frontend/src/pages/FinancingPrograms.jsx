import { useEffect, useState, useMemo } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Bank, Plus, PencilSimple, Trash, X, Sparkle, Lightning, Clock, Stack } from "@phosphor-icons/react";

const KIND_META = {
    standard: { label: "Standard APR", icon: Bank,      color: "bg-blue-100 text-blue-800" },
    buydown:  { label: "Buy-Down",     icon: Sparkle,   color: "bg-violet-100 text-violet-800" },
    promo:    { label: "0% Promo",     icon: Lightning, color: "bg-amber-100 text-amber-800" },
    deferred: { label: "Deferred",     icon: Clock,     color: "bg-emerald-100 text-emerald-800" },
};

const empty = (kind = "standard") => ({
    name: "", kind, apr: 9.99, base_apr: null, buydown_pct: 0, dealer_fee_pct: 5.0,
    term_months: 60, amort_months: 60, promo_months: 12, defer_months: 6, defer_interest_accrues: true, active: true,
});

const fmt$ = (v) => `$${(Number(v) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function FinancingPrograms() {
    const [programs, setPrograms] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeKind, setActiveKind] = useState("all");
    const [editing, setEditing] = useState(null);

    const load = async () => {
        try {
            const { data } = await api.get("/financing/programs");
            setPrograms(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []);

    const filtered = useMemo(() => activeKind === "all" ? programs : programs.filter((p) => p.kind === activeKind), [programs, activeKind]);
    const counts = useMemo(() => programs.reduce((acc, p) => ({ ...acc, [p.kind]: (acc[p.kind] || 0) + 1 }), { all: programs.length }), [programs]);

    const toggleActive = async (p) => {
        try { await api.patch(`/financing/programs/${p.id}`, { active: !p.active }); toast.success(p.active ? "Disabled" : "Enabled"); await load(); }
        catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    const remove = async (p) => {
        if (!confirm(`${p.is_system_default ? "Disable" : "Delete"} program "${p.name}"?`)) return;
        try { await api.delete(`/financing/programs/${p.id}`); toast.success("Removed"); await load(); }
        catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    return (
        <div className="space-y-5 max-w-7xl">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2"><Stack size={28}/> Financing Programs</h1>
                    <p className="text-sm text-slate-500 mt-1">Reusable plan templates for sales — Standard, Buy-Down, 0% Promo, and Deferred-Payment.</p>
                </div>
                <button onClick={() => setEditing(empty())} className="px-4 py-2 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm inline-flex items-center gap-1" data-testid="prog-new-btn"><Plus size={14}/> New program</button>
            </header>

            <div className="flex flex-wrap gap-2">
                {[["all","All"], ...Object.entries(KIND_META).map(([k, m]) => [k, m.label])].map(([k, label]) => (
                    <button key={k} onClick={() => setActiveKind(k)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold ${activeKind === k ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
                        data-testid={`prog-filter-${k}`}>
                        {label} <span className="opacity-60 ml-1">{counts[k] || 0}</span>
                    </button>
                ))}
            </div>

            {loading ? <div className="text-slate-500 text-sm">Loading…</div> : (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="prog-grid">
                    {filtered.map((p) => {
                        const meta = KIND_META[p.kind] || KIND_META.standard;
                        const Icon = meta.icon;
                        return (
                            <div key={p.id} className={`bg-white border-2 ${p.active ? "border-slate-200" : "border-dashed border-slate-300 opacity-60"} rounded-2xl p-4 space-y-3`} data-testid={`prog-card-${p.key}`}>
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center gap-2"><Icon size={20} weight="duotone"/><span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${meta.color}`}>{meta.label}</span></div>
                                    {p.is_system_default && <span className="text-[9px] uppercase font-bold bg-slate-100 px-2 py-0.5 rounded text-slate-500">default</span>}
                                </div>
                                <div className="font-bold text-slate-900">{p.name}</div>
                                <div className="grid grid-cols-2 gap-1 text-xs">
                                    {p.kind === "promo" ? (
                                        <><div className="text-slate-500">Equal payments</div><div className="text-right font-mono font-bold">{p.promo_months} mo</div></>
                                    ) : (
                                        <>
                                            <div className="text-slate-500">APR</div><div className="text-right font-mono font-bold">{p.apr}%</div>
                                            {p.base_apr && <><div className="text-slate-500">Base APR</div><div className="text-right font-mono text-slate-400 line-through">{p.base_apr}%</div></>}
                                            <div className="text-slate-500">Term</div><div className="text-right font-mono font-bold">{p.term_months}mo</div>
                                            {p.amort_months !== p.term_months && <><div className="text-slate-500">Amortization</div><div className="text-right font-mono font-bold">{p.amort_months}mo</div></>}
                                        </>
                                    )}
                                    {p.kind === "deferred" && <><div className="text-slate-500">Deferral</div><div className="text-right font-mono font-bold">{p.defer_months}mo{p.defer_interest_accrues ? " (interest accrues)" : " (no interest)"}</div></>}
                                    <div className="text-slate-500">Dealer fee</div><div className="text-right font-mono font-bold text-violet-700">{p.dealer_fee_pct}%</div>
                                </div>
                                <div className="flex gap-2 pt-2 border-t border-slate-100">
                                    <button onClick={() => toggleActive(p)} className={`flex-1 text-[11px] font-bold uppercase px-2 py-1 rounded ${p.active ? "bg-green-50 text-green-700 hover:bg-green-100" : "bg-slate-100 text-slate-500"}`} data-testid={`prog-toggle-${p.key}`}>
                                        {p.active ? "Active" : "Disabled"}
                                    </button>
                                    <button onClick={() => setEditing(p)} className="px-2 py-1 rounded border border-slate-200 hover:bg-slate-50" data-testid={`prog-edit-${p.key}`}><PencilSimple size={12}/></button>
                                    <button onClick={() => remove(p)} className="px-2 py-1 rounded border border-rose-200 text-rose-700 hover:bg-rose-50" data-testid={`prog-delete-${p.key}`}><Trash size={12}/></button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {editing && <ProgramModal initial={editing} onClose={() => setEditing(null)} onSaved={load}/>}
        </div>
    );
}

function ProgramModal({ initial, onClose, onSaved }) {
    const [f, setF] = useState(initial.id ? { ...initial } : initial);
    const isEdit = !!initial.id;
    const [quote, setQuote] = useState(null);
    const [busy, setBusy] = useState(false);
    const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

    useEffect(() => {
        // Live preview at $12k
        api.post("/financing/program-quote", { amount: 12000, program: f })
            .then(({ data }) => setQuote(data))
            .catch(() => setQuote(null));
    }, [f]); // eslint-disable-line

    const save = async () => {
        setBusy(true);
        try {
            const payload = { ...f };
            ["base_apr","promo_months","defer_months"].forEach((k) => { if (payload[k] === "" || payload[k] === null) delete payload[k]; });
            if (isEdit) await api.patch(`/financing/programs/${initial.id}`, payload);
            else await api.post("/financing/programs", payload);
            toast.success(isEdit ? "Saved" : "Created");
            onSaved(); onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl p-6 space-y-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="prog-modal">
                <div className="flex items-center justify-between">
                    <h2 className="font-bold text-lg">{isEdit ? "Edit program" : "New program"}</h2>
                    <button onClick={onClose}><X size={20}/></button>
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                    <div className="space-y-3">
                        <Input label="Program name" value={f.name} onChange={(v) => set("name", v)} testid="prog-name"/>
                        <Select label="Type" value={f.kind} onChange={(v) => set("kind", v)} testid="prog-kind"
                            options={Object.entries(KIND_META).map(([k, m]) => [k, m.label])}/>
                        {f.kind === "promo" ? (
                            <Input label="Promo length (months)" type="number" value={f.promo_months || 12} onChange={(v) => set("promo_months", Number(v))} testid="prog-promo"/>
                        ) : (
                            <>
                                <div className="grid grid-cols-2 gap-2">
                                    <Input label="APR %" type="number" step="0.01" value={f.apr} onChange={(v) => set("apr", Number(v))} testid="prog-apr"/>
                                    {f.kind === "buydown" && <Input label="Base APR %" type="number" step="0.01" value={f.base_apr || ""} onChange={(v) => set("base_apr", v ? Number(v) : null)} testid="prog-base-apr"/>}
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                    <Select label="Term (months)" value={f.term_months} onChange={(v) => set("term_months", Number(v))} testid="prog-term"
                                        options={[12,24,36,48,60,72,84,120].map((m) => [m, `${m} mo`])}/>
                                    <Select label="Amortization" value={f.amort_months} onChange={(v) => set("amort_months", Number(v))} testid="prog-amort"
                                        options={[12,24,36,60,84,120,180,240].map((m) => [m, `${m} mo`])}/>
                                </div>
                                {f.kind === "deferred" && (
                                    <>
                                        <Input label="Deferral months" type="number" value={f.defer_months || 6} onChange={(v) => set("defer_months", Number(v))} testid="prog-defer"/>
                                        <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={!!f.defer_interest_accrues} onChange={(e) => set("defer_interest_accrues", e.target.checked)}/>Interest accrues during deferral</label>
                                    </>
                                )}
                            </>
                        )}
                        <Input label="Dealer fee %" type="number" step="0.1" value={f.dealer_fee_pct} onChange={(v) => set("dealer_fee_pct", Number(v))} testid="prog-fee"/>
                        <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={!!f.active} onChange={(e) => set("active", e.target.checked)}/>Active (available to sales)</label>
                    </div>

                    <aside className="bg-slate-50 rounded-xl p-4 space-y-2">
                        <div className="text-xs font-bold uppercase tracking-wider text-slate-600">Live preview · $12,000 financed</div>
                        {quote ? (
                            <div className="space-y-1 text-sm">
                                <Row label="Monthly payment"        value={fmt$(quote.monthly_payment)} bold/>
                                {quote.balloon_payment > 0 && <Row label="Balloon at end of term"   value={fmt$(quote.balloon_payment)}/>}
                                <Row label="Total interest"         value={fmt$(quote.total_interest || 0)}/>
                                <Row label="Total customer payback" value={fmt$(quote.total_payback || 0)} bold/>
                                <hr className="my-2 border-slate-200"/>
                                <Row label="Dealer fee %"           value={`${quote.dealer_fee_pct}%`}/>
                                <Row label="Dealer fee $"           value={fmt$(quote.contractor_fee_dollars)}/>
                                <Row label="Net payout to you"      value={fmt$(quote.net_payout)} bold accent/>
                                {quote.customer_savings_vs_base > 0 && <Row label="Customer savings vs base APR" value={fmt$(quote.customer_savings_vs_base)}/>}
                                {quote.promo_months && <Row label="Equal payments" value={`${quote.promo_months} months @ 0%`}/>}
                                {quote.defer_months && <Row label="Deferred"  value={`${quote.defer_months} mo · ${quote.defer_interest_accrues ? "interest accrues" : "no interest"}`}/>}
                            </div>
                        ) : <div className="text-xs text-slate-400">Adjust values to see the quote…</div>}
                    </aside>
                </div>
                <button onClick={save} disabled={busy || !f.name} className="w-full px-5 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold disabled:opacity-50" data-testid="prog-save">{busy ? "Saving…" : (isEdit ? "Save changes" : "Create program")}</button>
            </div>
        </div>
    );
}

function Input({ label, value, onChange, type = "text", testid, step }) {
    return <label className="block"><span className="text-xs font-bold uppercase tracking-wider text-slate-600">{label}</span>
        <input type={type} step={step} value={value} onChange={(e) => onChange(e.target.value)}
            className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid={testid}/></label>;
}
function Select({ label, value, onChange, options, testid }) {
    return <label className="block"><span className="text-xs font-bold uppercase tracking-wider text-slate-600">{label}</span>
        <select value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid={testid}>
            {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select></label>;
}
function Row({ label, value, bold, accent }) {
    return <div className="flex justify-between"><span className="text-slate-500">{label}</span><span className={`font-mono ${bold ? "font-bold" : ""} ${accent ? "text-green-700" : ""}`}>{value}</span></div>;
}
