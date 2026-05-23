import { useEffect, useState } from "react";
import api, { API_BASE, formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Bank, Plus, Copy, CurrencyDollar, TrendUp, Calculator, ArrowsClockwise, X } from "@phosphor-icons/react";

const fmt$ = (v) => `$${(Number(v) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const STATUS_COLORS = {
    started: "bg-slate-100 text-slate-700",
    decisioned: "bg-blue-100 text-blue-800",
    signed: "bg-purple-100 text-purple-800",
    funded: "bg-green-100 text-green-800",
    declined: "bg-rose-100 text-rose-800",
    manual_review: "bg-amber-100 text-amber-800",
};

export default function FinancingContractor() {
    const [tab, setTab] = useState("pipeline");
    const [dash, setDash] = useState(null);
    const [apps, setApps] = useState([]);
    const [rentals, setRentals] = useState([]);
    const [showApp, setShowApp] = useState(false);
    const [showRental, setShowRental] = useState(false);
    const [showCalc, setShowCalc] = useState(false);
    const [showBuydown, setShowBuydown] = useState(null);

    const load = async () => {
        try {
            const [{ data: d }, { data: a }, { data: r }] = await Promise.all([
                api.get("/financing/dashboard"),
                api.get("/financing/applications"),
                api.get("/financing/rentals"),
            ]);
            setDash(d); setApps(a); setRentals(r);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { load(); }, []);

    return (
        <div className="space-y-5 max-w-7xl">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2"><Bank size={28}/> Fresh Cash Finance</h1>
                    <p className="text-sm text-slate-500 mt-1">Your contractor funding dashboard. Track applications, apply buy-downs, manage rentals.</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => setShowCalc(true)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm font-semibold inline-flex items-center gap-1" data-testid="fin-calc-btn"><Calculator size={14}/> Calculator</button>
                    <button onClick={() => setShowRental(true)} className="px-3 py-2 rounded-lg border border-slate-300 text-sm font-semibold inline-flex items-center gap-1" data-testid="fin-rental-btn"><Plus size={14}/> Rental</button>
                    <button onClick={() => setShowApp(true)} className="px-4 py-2 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm inline-flex items-center gap-1" data-testid="fin-new-app-btn"><Plus size={14}/> New application</button>
                </div>
            </header>

            {/* Dashboard tiles */}
            {dash && (
                <div className="grid sm:grid-cols-4 gap-3" data-testid="fin-dashboard-tiles">
                    <Tile label="Total funded" value={fmt$(dash.total_funded)} icon={CurrencyDollar} color="text-green-700" />
                    <Tile label="Pending volume" value={fmt$(dash.pending_amount)} icon={TrendUp} color="text-blue-700" />
                    <Tile label="Buy-down fees" value={fmt$(dash.total_buydown_fees)} icon={ArrowsClockwise} color="text-violet-700"/>
                    <Tile label="Active rentals" value={dash.rentals_active} icon={Bank} color="text-amber-700" />
                </div>
            )}

            {/* Pipeline counts */}
            {dash && (
                <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                    {Object.entries(dash.pipeline).map(([k, v]) => (
                        <div key={k} className={`rounded-xl px-3 py-2 ${STATUS_COLORS[k] || "bg-slate-100 text-slate-700"}`} data-testid={`fin-pipeline-${k}`}>
                            <div className="text-2xl font-extrabold">{v}</div>
                            <div className="text-[10px] uppercase tracking-wider">{k.replace(/_/g," ")}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-slate-200 flex gap-4">
                {[["pipeline","Applications"], ["rentals","Rentals"]].map(([k, label]) => (
                    <button key={k} onClick={() => setTab(k)}
                        className={`pb-3 text-sm font-bold ${tab === k ? "border-b-2 border-[#1D4ED8] text-[#1D4ED8]" : "text-slate-500"}`}
                        data-testid={`fin-tab-${k}`}>
                        {label}
                    </button>
                ))}
            </div>

            {tab === "pipeline" && (
                <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                            <tr><th className="p-3 text-left">Customer</th><th className="text-right p-3">Amount</th><th className="p-3 text-left">Status</th><th className="p-3 text-left">Offer</th><th className="p-3 text-left">Public link</th><th></th></tr>
                        </thead>
                        <tbody>
                            {apps.map((a) => (
                                <tr key={a.id} className="border-t border-slate-100" data-testid={`fin-app-${a.id}`}>
                                    <td className="p-3"><div className="font-bold">{a.customer_name}</div><div className="text-[10px] text-slate-500">{a.customer_email}</div></td>
                                    <td className="p-3 text-right font-mono">{fmt$(a.amount)}</td>
                                    <td className="p-3"><span className={`text-xs font-bold px-2 py-1 rounded ${STATUS_COLORS[a.status] || "bg-slate-100"}`}>{a.status}</span></td>
                                    <td className="p-3 text-xs">{a.offer ? `${a.offer.apr}% · ${a.offer.term_months}mo · ${fmt$(a.offer.monthly_payment)}/mo` : "—"}</td>
                                    <td className="p-3"><CopyLink path={`/finance/${a.id}`} app={a}/></td>
                                    <td className="p-3 text-right">{a.status === "decisioned" && a.offer && <button onClick={() => setShowBuydown(a)} className="text-xs font-semibold px-3 py-1 rounded border border-violet-300 text-violet-700 hover:bg-violet-50" data-testid={`fin-buydown-${a.id}`}>Buy-down</button>}</td>
                                </tr>
                            ))}
                            {!apps.length && <tr><td colSpan={6} className="p-8 text-center text-slate-500">No applications yet.</td></tr>}
                        </tbody>
                    </table>
                </div>
            )}

            {tab === "rentals" && (
                <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600"><tr><th className="p-3 text-left">Equipment</th><th className="p-3 text-left">Customer</th><th className="p-3 text-right">Value</th><th className="p-3 text-right">$/mo</th><th className="p-3 text-right">$/wk</th><th className="p-3 text-right">Balance</th></tr></thead>
                        <tbody>
                            {rentals.map((r) => (
                                <tr key={r.id} className="border-t border-slate-100" data-testid={`fin-rental-${r.id}`}>
                                    <td className="p-3 font-bold">{r.equipment_name}</td>
                                    <td className="p-3">{r.customer_name}</td>
                                    <td className="p-3 text-right font-mono">{fmt$(r.equipment_value)}</td>
                                    <td className="p-3 text-right font-mono">{fmt$(r.monthly_payment)}</td>
                                    <td className="p-3 text-right font-mono">{fmt$(r.weekly_payment)}</td>
                                    <td className="p-3 text-right font-mono">{fmt$(r.balance_remaining)}</td>
                                </tr>
                            ))}
                            {!rentals.length && <tr><td colSpan={6} className="p-8 text-center text-slate-500">No active rentals.</td></tr>}
                        </tbody>
                    </table>
                </div>
            )}

            {showApp && <NewAppModal onClose={() => setShowApp(false)} onCreated={load} />}
            {showRental && <NewRentalModal onClose={() => setShowRental(false)} onCreated={load} />}
            {showCalc && <CalcModal onClose={() => setShowCalc(false)} />}
            {showBuydown && <BuydownModal app={showBuydown} onClose={() => setShowBuydown(null)} onApplied={load} />}
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

function CopyLink({ app }) {
    const [copied, setCopied] = useState(false);
    const url = `${window.location.origin}/finance/${app.id}`;
    return (
        <div className="flex items-center gap-2 text-xs">
            <code className="truncate max-w-[180px] bg-slate-100 px-2 py-1 rounded">…/{app.id.slice(0, 8)}</code>
            <button onClick={() => { navigator.clipboard.writeText(url).catch(()=>{}); setCopied(true); setTimeout(()=>setCopied(false),1200); }} className="p-1 hover:bg-slate-100 rounded" data-testid={`fin-copy-${app.id}`}>
                {copied ? "✓" : <Copy size={12}/>}
            </button>
        </div>
    );
}

function Modal({ title, onClose, children, testid }) {
    return (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 space-y-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid={testid}>
                <div className="flex items-center justify-between"><h2 className="font-bold text-lg">{title}</h2><button onClick={onClose}><X size={20}/></button></div>
                {children}
            </div>
        </div>
    );
}

function NewAppModal({ onClose, onCreated }) {
    const [f, setF] = useState({ customer_name: "", customer_email: "", customer_phone: "", amount: "", term_months: 36 });
    const [busy, setBusy] = useState(false);
    const create = async () => {
        setBusy(true);
        try {
            const { data } = await api.post("/financing/applications", { ...f, amount: Number(f.amount), term_months: Number(f.term_months) });
            const url = `${window.location.origin}/finance/${data.id}`;
            await navigator.clipboard.writeText(url).catch(()=>{});
            toast.success(`Application created — link copied: …/${data.id.slice(0,8)}`);
            onCreated(); onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };
    return (
        <Modal title="New financing application" onClose={onClose} testid="fin-new-app-modal">
            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Customer name *" value={f.customer_name} onChange={(e) => setF({ ...f, customer_name: e.target.value })} data-testid="fin-new-name"/>
            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Email" value={f.customer_email} onChange={(e) => setF({ ...f, customer_email: e.target.value })}/>
            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Phone" value={f.customer_phone} onChange={(e) => setF({ ...f, customer_phone: e.target.value })}/>
            <div className="grid grid-cols-2 gap-2">
                <input type="number" className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Amount $ *" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="fin-new-amount"/>
                <input type="number" className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Term (months)" value={f.term_months} onChange={(e) => setF({ ...f, term_months: e.target.value })}/>
            </div>
            <button onClick={create} disabled={busy || !f.customer_name || !f.amount} className="w-full px-4 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold disabled:opacity-50" data-testid="fin-new-submit">{busy ? "Creating…" : "Create & copy link"}</button>
        </Modal>
    );
}

function NewRentalModal({ onClose, onCreated }) {
    const [f, setF] = useState({ customer_name: "", equipment_name: "", equipment_value: "", term_weeks: 52, deposit: 0 });
    const create = async () => {
        try {
            await api.post("/financing/rentals", { ...f, equipment_value: Number(f.equipment_value), term_weeks: Number(f.term_weeks), deposit: Number(f.deposit) });
            toast.success("Rental created"); onCreated(); onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    return (
        <Modal title="New rental agreement" onClose={onClose} testid="fin-new-rental-modal">
            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Customer name *" value={f.customer_name} onChange={(e) => setF({ ...f, customer_name: e.target.value })}/>
            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Equipment name *" value={f.equipment_name} onChange={(e) => setF({ ...f, equipment_name: e.target.value })}/>
            <input type="number" className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Equipment value $ *" value={f.equipment_value} onChange={(e) => setF({ ...f, equipment_value: e.target.value })}/>
            <div className="grid grid-cols-2 gap-2">
                <input type="number" className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Term (weeks)" value={f.term_weeks} onChange={(e) => setF({ ...f, term_weeks: e.target.value })}/>
                <input type="number" className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Deposit $" value={f.deposit} onChange={(e) => setF({ ...f, deposit: e.target.value })}/>
            </div>
            <button onClick={create} disabled={!f.customer_name || !f.equipment_name || !f.equipment_value} className="w-full px-4 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold disabled:opacity-50" data-testid="fin-rental-submit">Create rental</button>
        </Modal>
    );
}

function CalcModal({ onClose }) {
    const [amount, setAmount] = useState(5000);
    const [apr, setApr] = useState(9.99);
    const [term, setTerm] = useState(36);
    const [result, setResult] = useState(null);
    const calc = async () => {
        try {
            const { data } = await api.post("/financing/calculate", { amount: Number(amount), apr: Number(apr), term_months: Number(term) });
            setResult(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { calc(); /* eslint-disable-next-line */ }, [amount, apr, term]);
    return (
        <Modal title="Monthly payment calculator" onClose={onClose} testid="fin-calc-modal">
            <div className="grid grid-cols-3 gap-2">
                <label className="text-xs">Amount<input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="calc-amount"/></label>
                <label className="text-xs">APR %<input type="number" step="0.01" value={apr} onChange={(e) => setApr(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="calc-apr"/></label>
                <label className="text-xs">Term<input type="number" value={term} onChange={(e) => setTerm(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="calc-term"/></label>
            </div>
            {result && (
                <>
                    <div className="bg-slate-50 rounded-xl p-4 grid grid-cols-2 gap-2 text-center" data-testid="calc-result">
                        <div><div className="text-3xl font-extrabold">{fmt$(result.monthly_payment)}</div><div className="text-[10px] uppercase">monthly</div></div>
                        <div><div className="text-3xl font-extrabold">{fmt$(result.total_finance_charge)}</div><div className="text-[10px] uppercase">total interest</div></div>
                    </div>
                    <div className="max-h-60 overflow-y-auto border border-slate-200 rounded">
                        <table className="w-full text-xs">
                            <thead className="bg-slate-50 sticky top-0"><tr><th className="p-2 text-left">#</th><th className="p-2 text-right">Payment</th><th className="p-2 text-right">Principal</th><th className="p-2 text-right">Interest</th><th className="p-2 text-right">Balance</th></tr></thead>
                            <tbody>
                                {result.schedule.map((r) => (
                                    <tr key={r.n} className="border-t border-slate-100">
                                        <td className="p-2">{r.n}</td>
                                        <td className="p-2 text-right font-mono">{fmt$(r.payment)}</td>
                                        <td className="p-2 text-right font-mono">{fmt$(r.principal)}</td>
                                        <td className="p-2 text-right font-mono">{fmt$(r.interest)}</td>
                                        <td className="p-2 text-right font-mono">{fmt$(r.balance)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
        </Modal>
    );
}

function BuydownModal({ app, onClose, onApplied }) {
    const [fee, setFee] = useState(4);
    const [quote, setQuote] = useState(null);
    const [busy, setBusy] = useState(false);
    const refresh = async () => {
        try {
            const { data } = await api.post("/financing/buydown/quote", { application_id: app.id, fee_pct: Number(fee) });
            setQuote(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { refresh(); /* eslint-disable-next-line */ }, [fee]);
    const apply = async () => {
        setBusy(true);
        try {
            await api.post("/financing/buydown", { application_id: app.id, fee_pct: Number(fee) });
            toast.success("Buy-down applied — customer offer updated"); onApplied(); onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };
    return (
        <Modal title={`Buy-down for ${app.customer_name}`} onClose={onClose} testid="fin-buydown-modal">
            <p className="text-xs text-slate-500">Pay a contractor fee to lower your customer's APR. 1% fee = 0.5 APR point reduction.</p>
            <label className="text-xs">Fee % <input type="number" step="0.5" min={0} max={8} value={fee} onChange={(e) => setFee(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="buydown-fee-input"/></label>
            {quote && (
                <div className="bg-slate-50 rounded-xl p-3 space-y-1 text-sm" data-testid="buydown-quote">
                    <div className="flex justify-between"><span className="text-slate-500">Contractor fee:</span> <span className="font-mono font-bold">{fmt$(quote.contractor_fee)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">APR reduction:</span> <span className="font-mono font-bold">−{quote.apr_reduction_points} pts</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">New APR:</span> <span className="font-mono font-bold text-green-700">{quote.new_apr}%</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">New $/mo:</span> <span className="font-mono font-bold">{fmt$(quote.new_monthly_payment)}</span></div>
                    <div className="flex justify-between border-t pt-1 mt-1"><span className="text-slate-500">Customer lifetime savings:</span> <span className="font-mono font-bold text-green-700">{fmt$(quote.customer_lifetime_savings)}</span></div>
                </div>
            )}
            <button onClick={apply} disabled={busy} className="w-full px-4 py-3 rounded-xl bg-violet-700 text-white font-bold disabled:opacity-50" data-testid="buydown-apply">{busy ? "Applying…" : "Apply buy-down"}</button>
        </Modal>
    );
}
