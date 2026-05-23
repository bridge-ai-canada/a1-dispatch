import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Buildings, Plus, Trash, PencilSimple, Check, X } from "@phosphor-icons/react";

const empty = { name: "", address: "", city: "", state: "", postal_code: "", phone: "", email: "", active: true };

export default function Branches() {
    const [branches, setBranches] = useState([]);
    const [loading, setLoading] = useState(true);
    const [planLocked, setPlanLocked] = useState(false);
    const [showForm, setShowForm] = useState(false);
    const [editing, setEditing] = useState(null);
    const [form, setForm] = useState(empty);
    const [metrics, setMetrics] = useState({});

    const load = async () => {
        try {
            const { data } = await api.get("/branches");
            setBranches(data);
            // metrics in parallel
            const m = {};
            await Promise.all(data.map(async (b) => {
                try { const { data: mm } = await api.get(`/branches/${b.id}/metrics`); m[b.id] = mm; } catch {}
            }));
            setMetrics(m);
        } catch (e) {
            if (e.response?.status === 402) setPlanLocked(true);
            else toast.error(formatApiError(e.response?.data?.detail));
        } finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []);

    const startEdit = (b) => { setEditing(b.id); setForm({ ...empty, ...b }); setShowForm(true); };
    const startCreate = () => { setEditing(null); setForm(empty); setShowForm(true); };

    const save = async () => {
        try {
            if (editing) {
                await api.patch(`/branches/${editing}`, form);
                toast.success("Branch updated");
            } else {
                await api.post("/branches", form);
                toast.success("Branch created");
            }
            setShowForm(false); setEditing(null); setForm(empty);
            await load();
        } catch (e) {
            if (e.response?.status === 402) setPlanLocked(true);
            toast.error(formatApiError(e.response?.data?.detail));
        }
    };

    const remove = async (id) => {
        if (!confirm("Delete this branch? Jobs assigned to it will be unassigned.")) return;
        try { await api.delete(`/branches/${id}`); toast.success("Deleted"); await load(); }
        catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    if (planLocked) {
        return (
            <div className="max-w-2xl mx-auto py-12 text-center space-y-3" data-testid="branches-plan-locked">
                <Buildings size={48} className="mx-auto text-slate-300" />
                <h2 className="text-2xl font-extrabold text-slate-900">Multi-branch requires Pro</h2>
                <p className="text-slate-500">Upgrade to the Pro plan to manage multiple service locations and track per-branch metrics.</p>
                <a href="/app/settings/subscription" className="inline-block mt-3 px-5 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm">View plans</a>
            </div>
        );
    }

    return (
        <div className="space-y-5 max-w-5xl">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Branches</h1>
                    <p className="text-sm text-slate-500 mt-1">Sub-locations under your company. Assign jobs to branches and track per-location metrics.</p>
                </div>
                <button onClick={startCreate} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm" data-testid="branch-new-btn">
                    <Plus size={16}/> New branch
                </button>
            </header>

            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : branches.length === 0 ? (
                <div className="bg-slate-50 border border-dashed border-slate-200 rounded-2xl p-12 text-center">
                    <Buildings size={48} className="mx-auto text-slate-300 mb-3"/>
                    <div className="font-bold text-slate-900">No branches yet</div>
                    <div className="text-sm text-slate-500">Create your first branch to start tagging jobs by location.</div>
                </div>
            ) : (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {branches.map((b) => (
                        <div key={b.id} className="bg-white border border-slate-200 rounded-2xl p-4 space-y-3" data-testid={`branch-card-${b.id}`}>
                            <div className="flex items-start justify-between">
                                <div>
                                    <div className="font-bold text-slate-900">{b.name}</div>
                                    {b.city && <div className="text-xs text-slate-500">{b.city}{b.state ? `, ${b.state}` : ""}</div>}
                                </div>
                                {!b.active && <span className="text-[10px] uppercase font-bold bg-slate-200 px-2 py-0.5 rounded">Inactive</span>}
                            </div>
                            {metrics[b.id] && (
                                <div className="grid grid-cols-3 text-center gap-1 pt-2 border-t border-slate-100">
                                    <div><div className="text-lg font-bold text-slate-900">{metrics[b.id].jobs_total}</div><div className="text-[10px] uppercase text-slate-500">Jobs</div></div>
                                    <div><div className="text-lg font-bold text-slate-900">{metrics[b.id].jobs_open}</div><div className="text-[10px] uppercase text-slate-500">Open</div></div>
                                    <div><div className="text-lg font-bold text-green-700">${(metrics[b.id].revenue_paid || 0).toLocaleString()}</div><div className="text-[10px] uppercase text-slate-500">Revenue</div></div>
                                </div>
                            )}
                            <div className="flex gap-2">
                                <button onClick={() => startEdit(b)} className="flex-1 text-xs font-semibold px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 inline-flex items-center justify-center gap-1" data-testid={`branch-edit-${b.id}`}><PencilSimple size={12}/>Edit</button>
                                <button onClick={() => remove(b.id)} className="text-xs font-semibold px-3 py-2 rounded-lg border border-rose-200 text-rose-700 hover:bg-rose-50 inline-flex items-center gap-1" data-testid={`branch-delete-${b.id}`}><Trash size={12}/></button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {showForm && (
                <div className="fixed inset-0 bg-black/40 z-40 grid place-items-center p-4" onClick={() => setShowForm(false)}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between">
                            <h2 className="font-bold text-lg">{editing ? "Edit branch" : "New branch"}</h2>
                            <button onClick={() => setShowForm(false)}><X size={20}/></button>
                        </div>
                        <div className="space-y-2">
                            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="branch-form-name"/>
                            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Street address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}/>
                            <div className="grid grid-cols-3 gap-2">
                                <input className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="City" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })}/>
                                <input className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="State" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })}/>
                                <input className="h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Zip" value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })}/>
                            </div>
                            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}/>
                            <input className="w-full h-10 px-3 rounded border border-slate-300 text-sm" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}/>
                            <label className="inline-flex items-center gap-2 text-sm">
                                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })}/>
                                Active
                            </label>
                        </div>
                        <button onClick={save} disabled={!form.name} className="w-full px-4 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold disabled:opacity-50 inline-flex items-center justify-center gap-2" data-testid="branch-form-save"><Check size={16}/> {editing ? "Save" : "Create branch"}</button>
                    </div>
                </div>
            )}
        </div>
    );
}
