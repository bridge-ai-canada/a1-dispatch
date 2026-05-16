import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, X } from "@phosphor-icons/react";

export default function Customers() {
    const [items, setItems] = useState([]);
    const [open, setOpen] = useState(false);
    const load = () => api.get("/customers").then((r) => setItems(r.data));
    useEffect(() => { load(); }, []);

    return (
        <div data-testid="customers-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">CRM</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Customers</h1>
                </div>
                <button onClick={() => setOpen(true)} data-testid="add-customer-button"
                    className="bg-[#DC2626] text-white px-5 py-2.5 font-semibold hover:bg-[#B91C1C] flex items-center gap-2">
                    <Plus weight="bold" /> Add Customer
                </button>
            </div>

            <div className="border border-slate-200 overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr className="text-left">
                            <th className="px-4 py-3 font-semibold">Name</th>
                            <th className="px-4 py-3 font-semibold">Phone</th>
                            <th className="px-4 py-3 font-semibold">Email</th>
                            <th className="px-4 py-3 font-semibold">Address</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {items.length === 0 && (
                            <tr><td colSpan={4} className="p-12 text-center text-slate-500">No customers yet.</td></tr>
                        )}
                        {items.map((c) => (
                            <tr key={c.id} className="hover:bg-slate-50">
                                <td className="px-4 py-3 font-medium">{c.name}</td>
                                <td className="px-4 py-3 text-slate-600">{c.phone || "—"}</td>
                                <td className="px-4 py-3 text-slate-600">{c.email || "—"}</td>
                                <td className="px-4 py-3 text-slate-600">{c.address || "—"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {open && <CustomerModal onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load(); }} />}
        </div>
    );
}

function CustomerModal({ onClose, onSaved }) {
    const [form, setForm] = useState({ name: "", phone: "", email: "", address: "" });
    const [saving, setSaving] = useState(false);
    const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post("/customers", form);
            toast.success("Customer added");
            onSaved();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        } finally { setSaving(false); }
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-md border border-slate-300" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                    <h2 className="font-display text-2xl font-extrabold tracking-tighter">Add Customer</h2>
                    <button onClick={onClose}><X size={20} /></button>
                </div>
                <form onSubmit={submit} className="p-6 space-y-3">
                    <input required placeholder="Name" value={form.name} onChange={update("name")} data-testid="customer-name-input"
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <input placeholder="Phone" value={form.phone} onChange={update("phone")}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <input type="email" placeholder="Email" value={form.email} onChange={update("email")}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <input placeholder="Address" value={form.address} onChange={update("address")}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <button type="submit" disabled={saving} data-testid="customer-submit-button"
                        className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                        {saving ? "Saving..." : "Add"}
                    </button>
                </form>
            </div>
        </div>
    );
}
