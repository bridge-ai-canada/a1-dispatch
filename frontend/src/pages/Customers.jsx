import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, X, MagnifyingGlass, Tag, ArrowUpRight } from "@phosphor-icons/react";

const STATUS = ["lead", "prospect", "active", "churned"];
const STATUS_COLORS = {
    lead: "bg-amber-50 text-amber-700 border-amber-300",
    prospect: "bg-blue-50 text-[#1D4ED8] border-blue-300",
    active: "bg-emerald-50 text-emerald-700 border-emerald-300",
    churned: "bg-slate-100 text-slate-500 border-slate-300",
};

export default function Customers() {
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [q, setQ] = useState("");
    const [status, setStatus] = useState("");
    const [tag, setTag] = useState("");
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(true);

    const load = () => {
        setLoading(true);
        const params = new URLSearchParams();
        if (q) params.set("q", q);
        if (status) params.set("status", status);
        if (tag) params.set("tag", tag);
        api.get(`/customers?${params}`).then((r) => {
            // Response is now {items, total, has_more, limit, skip}
            setItems(r.data.items || r.data);
            setTotal(r.data.total ?? (Array.isArray(r.data) ? r.data.length : 0));
        }).finally(() => setLoading(false));
    };
    useEffect(() => {
        const t = setTimeout(load, 250);
        return () => clearTimeout(t);
    }, [q, status, tag]); // eslint-disable-line

    const allTags = useMemo(() => {
        const set = new Set();
        items.forEach((c) => (c.tags || []).forEach((t) => set.add(t)));
        return Array.from(set);
    }, [items]);

    return (
        <div data-testid="customers-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">CRM</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Customers</h1>
                    <p className="text-sm text-slate-500 mt-2">{total} {total === 1 ? "record" : "records"}{items.length < total && ` · showing ${items.length}`}</p>
                </div>
                <button onClick={() => setOpen(true)} data-testid="add-customer-button"
                    className="bg-[#DC2626] text-white px-5 py-2.5 font-semibold hover:bg-[#B91C1C] flex items-center gap-2">
                    <Plus weight="bold" /> New customer
                </button>
            </div>

            <div className="flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-64">
                    <MagnifyingGlass size={16} className="absolute left-3 top-3 text-slate-400" />
                    <input value={q} onChange={(e) => setQ(e.target.value)} data-testid="customer-search-input"
                        placeholder="Search name, phone, email, address..."
                        className="w-full border border-slate-300 pl-9 pr-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                </div>
                <div className="flex gap-1">
                    {["", ...STATUS].map((s) => (
                        <button key={s || "all"} onClick={() => setStatus(s)}
                            data-testid={`status-filter-${s || "all"}`}
                            className={`px-3 py-2 text-xs font-semibold uppercase tracking-wider border ${
                                status === s ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 hover:bg-slate-50"
                            }`}>
                            {s || "All"}
                        </button>
                    ))}
                </div>
            </div>

            {allTags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                    <Tag size={14} className="text-slate-400 mr-1" />
                    {allTags.map((t) => (
                        <button key={t} onClick={() => setTag(tag === t ? "" : t)}
                            data-testid={`tag-pill-${t}`}
                            className={`text-xs px-2 py-0.5 border ${tag === t ? "border-[#DC2626] bg-[#DC2626] text-white" : "border-slate-300 hover:bg-slate-50"}`}>
                            {t}
                        </button>
                    ))}
                </div>
            )}

            <div className="border border-slate-200 overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr className="text-left">
                            <th className="px-4 py-3 font-semibold">Name</th>
                            <th className="px-4 py-3 font-semibold">Phone</th>
                            <th className="px-4 py-3 font-semibold">Email</th>
                            <th className="px-4 py-3 font-semibold">Status</th>
                            <th className="px-4 py-3 font-semibold">Tags</th>
                            <th className="px-4 py-3 font-semibold text-right"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {loading && <tr><td colSpan={6} className="p-8 text-center text-slate-500">Loading...</td></tr>}
                        {!loading && items.length === 0 && (
                            <tr><td colSpan={6} className="p-12 text-center text-slate-500">No customers match.</td></tr>
                        )}
                        {items.map((c) => (
                            <tr key={c.id} className="hover:bg-slate-50">
                                <td className="px-4 py-3">
                                    <Link to={`/app/customers/${c.id}`} data-testid={`customer-link-${c.id}`} className="font-medium hover:underline">{c.name}</Link>
                                </td>
                                <td className="px-4 py-3 text-slate-600">{c.phone || "—"}</td>
                                <td className="px-4 py-3 text-slate-600">{c.email || "—"}</td>
                                <td className="px-4 py-3">
                                    <span className={`text-[10px] px-2 py-0.5 border font-semibold uppercase tracking-wider ${STATUS_COLORS[c.status || "active"]}`}>
                                        {c.status || "active"}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <div className="flex flex-wrap gap-1">
                                        {(c.tags || []).slice(0,3).map((t) => (
                                            <span key={t} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-700">{t}</span>
                                        ))}
                                    </div>
                                </td>
                                <td className="px-4 py-3 text-right">
                                    <Link to={`/app/customers/${c.id}`} className="text-xs text-[#1D4ED8] hover:underline inline-flex items-center gap-1">
                                        Open <ArrowUpRight size={12} />
                                    </Link>
                                </td>
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
    const [form, setForm] = useState({ name: "", phone: "", email: "", address: "", status: "active", tags: [], tagInput: "" });
    const [saving, setSaving] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const { tagInput, ...payload } = form;
            await api.post("/customers", payload);
            toast.success("Customer added");
            onSaved();
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
        finally { setSaving(false); }
    };

    const addTag = () => {
        const t = form.tagInput.trim();
        if (t && !form.tags.includes(t)) {
            setForm({ ...form, tags: [...form.tags, t], tagInput: "" });
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-md border border-slate-300" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                    <h2 className="font-display text-2xl font-extrabold tracking-tighter">New customer</h2>
                    <button onClick={onClose}><X size={20} /></button>
                </div>
                <form onSubmit={submit} className="p-6 space-y-3">
                    <input required placeholder="Name" value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                        data-testid="customer-name-input"
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <div className="grid grid-cols-2 gap-3">
                        <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})}
                            className="w-full border border-slate-300 px-3 py-2.5" />
                        <input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})}
                            className="w-full border border-slate-300 px-3 py-2.5" />
                    </div>
                    <input placeholder="Address" value={form.address} onChange={(e) => setForm({...form, address: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <select value={form.status} onChange={(e) => setForm({...form, status: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                        {STATUS.map((s) => <option key={s}>{s}</option>)}
                    </select>
                    <div className="flex gap-2">
                        <input placeholder="Add tag (press +)" value={form.tagInput} onChange={(e) => setForm({...form, tagInput: e.target.value})}
                            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                            className="flex-1 border border-slate-300 px-3 py-2.5" />
                        <button type="button" onClick={addTag} className="px-3 border border-slate-300 hover:bg-slate-50">+</button>
                    </div>
                    {form.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                            {form.tags.map((t) => (
                                <span key={t} className="text-xs px-2 py-0.5 bg-slate-100 inline-flex items-center gap-1">
                                    {t}
                                    <button type="button" onClick={() => setForm({...form, tags: form.tags.filter((x) => x !== t)})}>×</button>
                                </span>
                            ))}
                        </div>
                    )}
                    <button type="submit" disabled={saving} data-testid="customer-submit-button"
                        className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                        {saving ? "Saving..." : "Add"}
                    </button>
                </form>
            </div>
        </div>
    );
}
