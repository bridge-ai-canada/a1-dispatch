import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash, FileText, X } from "@phosphor-icons/react";

const TIER_KEYS = ["good", "better", "best"];

function emptyTier(key) {
    return { key, name: key[0].toUpperCase()+key.slice(1), summary: "", line_items: [], addons: [], featured: key === "better" };
}

function fmtMoney(v) { return `$${(Number(v)||0).toFixed(2)}`; }

export default function Templates() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [open, setOpen] = useState(false);
    const [form, setForm] = useState({
        name: "", kind: "estimate", description: "", tax_rate: 0, terms: "",
        tiers: TIER_KEYS.map(emptyTier),
        line_items: [],
    });

    const load = async () => {
        try {
            const { data } = await api.get("/templates");
            setItems(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []);

    const save = async () => {
        if (!form.name.trim()) return toast.error("Name required");
        try {
            const body = { ...form };
            if (form.kind === "estimate") delete body.line_items;
            else delete body.tiers;
            await api.post("/templates", body);
            toast.success("Template saved");
            setOpen(false);
            setForm({ name: "", kind: "estimate", description: "", tax_rate: 0, terms: "",
                tiers: TIER_KEYS.map(emptyTier), line_items: [] });
            load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const remove = async (id) => {
        if (!window.confirm("Delete this template?")) return;
        try {
            await api.delete(`/templates/${id}`);
            load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const updateTierItem = (tIdx, iIdx, patch) => {
        setForm((f) => ({ ...f, tiers: f.tiers.map((t,i) => i!==tIdx ? t : {
            ...t, line_items: t.line_items.map((li,j) => j!==iIdx ? li : {...li, ...patch}),
        })}));
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Templates</h1>
                    <p className="text-sm text-slate-500">Reusable Good/Better/Best presets and invoice templates.</p>
                </div>
                <button onClick={() => setOpen(true)}
                    className="inline-flex items-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-semibold px-4 py-2.5 rounded-lg shadow-sm"
                    data-testid="new-template-button">
                    <Plus size={18} weight="bold"/> New template
                </button>
            </div>

            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : items.length === 0 ? (
                <div className="text-center py-16 rounded-2xl border-2 border-dashed border-slate-200">
                    <FileText size={48} className="mx-auto text-slate-300"/>
                    <p className="mt-3 text-slate-500">No templates yet. Create one to speed up future proposals.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {items.map((t) => (
                        <div key={t.id} className="rounded-2xl border border-slate-200 bg-white p-5">
                            <div className="flex items-start justify-between">
                                <div>
                                    <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{t.kind}</div>
                                    <div className="mt-0.5 text-lg font-extrabold tracking-tight">{t.name}</div>
                                </div>
                                <button onClick={() => remove(t.id)} className="text-slate-400 hover:text-[#DC2626]">
                                    <Trash size={16}/>
                                </button>
                            </div>
                            {t.description && <p className="mt-2 text-sm text-slate-600">{t.description}</p>}
                            {t.kind === "estimate" && (
                                <div className="mt-3 flex gap-1.5 text-xs">
                                    {(t.tiers||[]).map((ti) => (
                                        <span key={ti.key} className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">{ti.name}</span>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Modal */}
            {open && (
                <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-end sm:items-center justify-center p-2 sm:p-4">
                    <div className="bg-white rounded-3xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
                        <div className="flex items-start justify-between">
                            <h3 className="text-xl font-extrabold tracking-tight">New template</h3>
                            <button onClick={() => setOpen(false)} className="p-2 text-slate-400 hover:text-slate-700">
                                <X size={20}/>
                            </button>
                        </div>

                        <div className="mt-4 space-y-3">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Name</label>
                                    <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                        value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                                        data-testid="template-name-input"/>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Kind</label>
                                    <select className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                        value={form.kind} onChange={(e) => setForm({...form, kind: e.target.value})}>
                                        <option value="estimate">Estimate (Good/Better/Best)</option>
                                        <option value="invoice">Invoice (single tier)</option>
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Description</label>
                                <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                    value={form.description} onChange={(e) => setForm({...form, description: e.target.value})}/>
                            </div>

                            {form.kind === "estimate" ? (
                                <div className="space-y-3">
                                    {form.tiers.map((tier, idx) => (
                                        <div key={tier.key} className="rounded-xl border border-slate-200 p-3">
                                            <div className="flex items-center gap-2 mb-2">
                                                <input className="font-semibold text-sm flex-1 px-2 py-1 border border-slate-200 rounded"
                                                    value={tier.name}
                                                    onChange={(e) => setForm({...form, tiers: form.tiers.map((t,i) => i!==idx ? t : {...t, name: e.target.value})})}/>
                                                <button onClick={() => setForm({...form, tiers: form.tiers.map((t,i) => i!==idx ? t : {
                                                    ...t, line_items: [...t.line_items, { description: "", qty: 1, unit_price: 0, taxable: true, kind: "service" }],
                                                })})}
                                                    className="text-xs text-[#1D4ED8] font-semibold hover:underline">+ Add item</button>
                                            </div>
                                            {tier.line_items.map((li, li_idx) => (
                                                <div key={li_idx} className="flex gap-1 mb-1">
                                                    <input className="flex-1 text-sm px-2 py-1 border border-slate-200 rounded"
                                                        placeholder="Description" value={li.description}
                                                        onChange={(e) => updateTierItem(idx, li_idx, { description: e.target.value })}/>
                                                    <input type="number" className="w-16 text-sm px-2 py-1 border border-slate-200 rounded"
                                                        value={li.qty} onChange={(e) => updateTierItem(idx, li_idx, { qty: parseFloat(e.target.value)||0 })}/>
                                                    <input type="number" className="w-24 text-sm px-2 py-1 border border-slate-200 rounded"
                                                        value={li.unit_price} onChange={(e) => updateTierItem(idx, li_idx, { unit_price: parseFloat(e.target.value)||0 })}/>
                                                </div>
                                            ))}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-slate-200 p-3">
                                    <div className="flex items-center justify-between mb-2">
                                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Line items</span>
                                        <button onClick={() => setForm({...form, line_items: [...form.line_items, { description: "", qty: 1, unit_price: 0, taxable: true, kind: "service" }]})}
                                            className="text-xs text-[#1D4ED8] font-semibold hover:underline">+ Add item</button>
                                    </div>
                                    {form.line_items.map((li, i) => (
                                        <div key={i} className="flex gap-1 mb-1">
                                            <input className="flex-1 text-sm px-2 py-1 border border-slate-200 rounded"
                                                placeholder="Description" value={li.description}
                                                onChange={(e) => setForm({...form, line_items: form.line_items.map((x,j) => j!==i ? x : {...x, description: e.target.value})})}/>
                                            <input type="number" className="w-16 text-sm px-2 py-1 border border-slate-200 rounded"
                                                value={li.qty}
                                                onChange={(e) => setForm({...form, line_items: form.line_items.map((x,j) => j!==i ? x : {...x, qty: parseFloat(e.target.value)||0})})}/>
                                            <input type="number" className="w-24 text-sm px-2 py-1 border border-slate-200 rounded"
                                                value={li.unit_price}
                                                onChange={(e) => setForm({...form, line_items: form.line_items.map((x,j) => j!==i ? x : {...x, unit_price: parseFloat(e.target.value)||0})})}/>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Default tax rate (%)</label>
                                    <input type="number" step="0.01" className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                        value={form.tax_rate} onChange={(e) => setForm({...form, tax_rate: parseFloat(e.target.value)||0})}/>
                                </div>
                            </div>
                            <button onClick={save}
                                className="w-full bg-[#DC2626] hover:bg-[#B91C1C] text-white font-bold py-3 rounded-xl"
                                data-testid="save-template-button">
                                Save template
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
