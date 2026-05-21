import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft, FloppyDisk, PaperPlaneTilt, Plus, Trash } from "@phosphor-icons/react";

function emptyInvoice() {
    return {
        title: "Services rendered",
        customer_name: "", customer_email: "", customer_phone: "", address: "",
        tax_rate: 0,
        discount: { type: "percent", value: 0 },
        deposit: { type: "none", value: 0 },
        due_in_days: 14,
        terms: "Payment due within 14 days. Late payments may incur a 1.5% monthly fee.",
        notes: "",
        line_items: [],
    };
}

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }

export default function InvoiceBuilder() {
    const navigate = useNavigate();
    const { id } = useParams();
    const isEdit = !!id;
    const [form, setForm] = useState(emptyInvoice());
    const [doc, setDoc] = useState(null);
    const [loading, setLoading] = useState(isEdit);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (isEdit) {
            api.get(`/invoices/${id}`).then((r) => {
                const d = r.data; setDoc(d);
                setForm({
                    title: d.title || "Services rendered",
                    customer_name: d.customer_name || "", customer_email: d.customer_email || "",
                    customer_phone: d.customer_phone || "", address: d.address || "",
                    tax_rate: d.tax_rate || 0,
                    discount: d.discount || { type: "percent", value: 0 },
                    deposit: d.deposit || { type: "none", value: 0 },
                    due_in_days: 14,
                    terms: d.terms || "", notes: d.notes || "",
                    line_items: d.line_items || [],
                });
            }).catch((e) => toast.error(formatApiError(e.response?.data?.detail)))
            .finally(() => setLoading(false));
        }
    }, [id, isEdit]);

    const totals = (() => {
        const subtotal = (form.line_items||[]).reduce((s,i)=>s+(Number(i.qty)||0)*(Number(i.unit_price)||0),0);
        const taxable = (form.line_items||[]).filter(i=>i.taxable!==false).reduce((s,i)=>s+(Number(i.qty)||0)*(Number(i.unit_price)||0),0);
        const dval = Number(form.discount.value)||0;
        const discountAmount = form.discount.type === "percent" ? subtotal*dval/100 : Math.min(dval,subtotal);
        const ratio = subtotal > 0 ? (subtotal-discountAmount)/subtotal : 1;
        const taxAmount = (taxable*ratio) * (Number(form.tax_rate)||0)/100;
        const total = subtotal - discountAmount + taxAmount;
        const depVal = Number(form.deposit.value)||0;
        const depAmount = form.deposit.type === "percent" ? total*depVal/100
            : form.deposit.type === "fixed" ? Math.min(depVal,total) : 0;
        return { subtotal, discountAmount, taxAmount, total, depAmount };
    })();

    const update = (i, patch) => setForm((f) => ({
        ...f, line_items: f.line_items.map((li,j) => j===i ? {...li, ...patch} : li),
    }));
    const add = () => setForm((f) => ({
        ...f, line_items: [...f.line_items, { description: "", qty: 1, unit_price: 0, taxable: true, kind: "service" }],
    }));
    const remove = (i) => setForm((f) => ({
        ...f, line_items: f.line_items.filter((_,j) => j !== i),
    }));

    const save = async (also) => {
        if (!form.customer_name && !form.customer_email) return toast.error("Please add customer name or email");
        if (!form.line_items.length) return toast.error("Please add at least one line item");
        setSaving(true);
        try {
            const body = {
                ...form,
                tax_rate: Number(form.tax_rate)||0,
                discount: { type: form.discount.type, value: Number(form.discount.value)||0 },
                deposit: { type: form.deposit.type, value: Number(form.deposit.value)||0 },
                due_in_days: Number(form.due_in_days)||14,
            };
            const r = isEdit
                ? await api.put(`/invoices/${id}`, body)
                : await api.post("/invoices", body);
            toast.success(isEdit ? "Invoice updated" : "Invoice created");
            if (also === "send") {
                await api.post(`/invoices/${r.data.id}/send`);
                toast.success("Invoice emailed to customer");
            }
            navigate(`/app/invoices/${r.data.id}`);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setSaving(false); }
    };

    if (loading) return <div className="text-sm text-slate-500">Loading…</div>;

    return (
        <div className="space-y-6 pb-20">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                    <button onClick={() => navigate("/app/invoices")}
                        className="p-2 -ml-2 text-slate-600 hover:text-slate-900">
                        <ArrowLeft size={20}/>
                    </button>
                    <div>
                        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
                            {isEdit ? `Edit Invoice ${doc?.number||""}` : "New Invoice"}
                        </h1>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => save("draft")} disabled={saving}
                        className="inline-flex items-center gap-2 bg-white border border-slate-200 hover:border-slate-400 px-4 py-2.5 rounded-lg font-semibold text-slate-700"
                        data-testid="save-invoice-button">
                        <FloppyDisk size={18}/> Save Draft
                    </button>
                    <button onClick={() => save("send")} disabled={saving}
                        className="inline-flex items-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white px-4 py-2.5 rounded-lg font-semibold shadow-sm"
                        data-testid="save-send-invoice-button">
                        <PaperPlaneTilt size={18} weight="fill"/> Save & Send
                    </button>
                </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="sm:col-span-2">
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Invoice title</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.title} onChange={(e) => setForm({...form, title: e.target.value})}
                            data-testid="invoice-title-input"/>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer name</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.customer_name} onChange={(e) => setForm({...form, customer_name: e.target.value})}/>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer email</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg" type="email"
                            value={form.customer_email} onChange={(e) => setForm({...form, customer_email: e.target.value})}/>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Customer phone</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.customer_phone} onChange={(e) => setForm({...form, customer_phone: e.target.value})}/>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Service address</label>
                        <input className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                            value={form.address} onChange={(e) => setForm({...form, address: e.target.value})}/>
                    </div>
                </div>
            </div>

            {/* Line items */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="font-bold text-slate-900">Line items</h3>
                    <button onClick={add}
                        className="inline-flex items-center gap-2 text-sm font-semibold text-[#1D4ED8] hover:underline"
                        data-testid="add-line-item-button">
                        <Plus size={14} weight="bold"/> Add item
                    </button>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="text-xs uppercase tracking-wider text-slate-500">
                            <tr>
                                <th className="text-left px-2 py-2">Description</th>
                                <th className="text-right px-2 py-2">Qty</th>
                                <th className="text-right px-2 py-2">Price</th>
                                <th className="text-center px-2 py-2">Tax</th>
                                <th className="text-right px-2 py-2">Amount</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {form.line_items.length === 0 && (
                                <tr><td colSpan={6} className="text-center text-slate-400 py-6">No line items yet. Click "Add item" above.</td></tr>
                            )}
                            {form.line_items.map((li, i) => (
                                <tr key={i} className="border-t border-slate-100">
                                    <td className="px-2 py-2">
                                        <input className="w-full px-2 py-1.5 border border-slate-200 rounded"
                                            placeholder="Description"
                                            value={li.description||""}
                                            onChange={(e) => update(i, { description: e.target.value })}/>
                                    </td>
                                    <td className="px-2 py-2 w-20">
                                        <input type="number" step="0.5" min="0"
                                            className="w-full px-2 py-1.5 border border-slate-200 rounded text-right"
                                            value={li.qty}
                                            onChange={(e) => update(i, { qty: parseFloat(e.target.value)||0 })}/>
                                    </td>
                                    <td className="px-2 py-2 w-28">
                                        <input type="number" step="0.01" min="0"
                                            className="w-full px-2 py-1.5 border border-slate-200 rounded text-right"
                                            value={li.unit_price}
                                            onChange={(e) => update(i, { unit_price: parseFloat(e.target.value)||0 })}/>
                                    </td>
                                    <td className="px-2 py-2 text-center">
                                        <input type="checkbox" checked={li.taxable !== false}
                                            onChange={(e) => update(i, { taxable: e.target.checked })}/>
                                    </td>
                                    <td className="px-2 py-2 text-right font-semibold">
                                        {fmtMoney((li.qty||0)*(li.unit_price||0))}
                                    </td>
                                    <td className="px-2 py-2 w-10">
                                        <button onClick={() => remove(i)} className="text-slate-400 hover:text-[#DC2626]">
                                            <Trash size={16}/>
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Settings + totals */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
                    <h3 className="font-bold text-slate-900">Adjustments</h3>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tax rate (%)</label>
                            <input type="number" step="0.01" className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                value={form.tax_rate}
                                onChange={(e) => setForm({...form, tax_rate: parseFloat(e.target.value)||0})}/>
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
                                    onChange={(e) => setForm({...form, discount: {...form.discount, value: parseFloat(e.target.value)||0}})}/>
                            </div>
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Due in (days)</label>
                            <input type="number" min="1" className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg"
                                value={form.due_in_days}
                                onChange={(e) => setForm({...form, due_in_days: parseInt(e.target.value)||14})}/>
                        </div>
                        <div>
                            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Deposit required</label>
                            <div className="flex gap-1.5 mt-1">
                                <select className="px-2 py-2 border border-slate-200 rounded-lg text-sm"
                                    value={form.deposit.type}
                                    onChange={(e) => setForm({...form, deposit: {...form.deposit, type: e.target.value}})}>
                                    <option value="none">None</option>
                                    <option value="percent">%</option>
                                    <option value="fixed">$</option>
                                </select>
                                {form.deposit.type !== "none" && (
                                    <input type="number" step="0.01" className="flex-1 px-3 py-2 border border-slate-200 rounded-lg"
                                        value={form.deposit.value}
                                        onChange={(e) => setForm({...form, deposit: {...form.deposit, value: parseFloat(e.target.value)||0}})}/>
                                )}
                            </div>
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Terms</label>
                        <textarea className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg" rows={2}
                            value={form.terms} onChange={(e) => setForm({...form, terms: e.target.value})}/>
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-900 text-white p-5">
                    <h3 className="font-bold mb-3">Summary</h3>
                    <div className="space-y-2 text-sm">
                        <div className="flex justify-between text-slate-300"><span>Subtotal</span><span>{fmtMoney(totals.subtotal)}</span></div>
                        {totals.discountAmount > 0 && (
                            <div className="flex justify-between text-slate-300"><span>Discount</span><span>-{fmtMoney(totals.discountAmount)}</span></div>
                        )}
                        {totals.taxAmount > 0 && (
                            <div className="flex justify-between text-slate-300"><span>Tax</span><span>{fmtMoney(totals.taxAmount)}</span></div>
                        )}
                        <div className="border-t border-slate-700 pt-2 flex justify-between items-baseline">
                            <span className="text-xs uppercase tracking-wider text-slate-400">Total</span>
                            <span className="text-3xl font-extrabold">{fmtMoney(totals.total)}</span>
                        </div>
                        {totals.depAmount > 0 && (
                            <div className="text-xs text-emerald-400 font-semibold">
                                Deposit due: {fmtMoney(totals.depAmount)}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
