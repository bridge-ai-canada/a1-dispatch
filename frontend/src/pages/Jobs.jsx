import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Plus, X, CreditCard } from "@phosphor-icons/react";
import { Link } from "react-router-dom";

const STATUS = ["unscheduled", "scheduled", "in_progress", "completed", "cancelled"];
const STATUS_COLORS = {
    unscheduled: "bg-slate-100 text-slate-700 border-slate-300",
    scheduled: "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30",
    in_progress: "bg-amber-50 text-amber-700 border-amber-400",
    completed: "bg-emerald-50 text-emerald-700 border-emerald-400",
    cancelled: "bg-red-50 text-[#DC2626] border-[#DC2626]/40",
};

export default function Jobs() {
    const [jobs, setJobs] = useState([]);
    const [team, setTeam] = useState([]);
    const [filter, setFilter] = useState("all");
    const [open, setOpen] = useState(false);
    const [editing, setEditing] = useState(null);
    const [loading, setLoading] = useState(true);

    const load = () => {
        api.get("/jobs").then((r) => setJobs(r.data)).finally(() => setLoading(false));
        api.get("/team").then((r) => setTeam(r.data));
    };
    useEffect(() => { load(); }, []);

    const filtered = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);

    const pay = async (job) => {
        try {
            const { data } = await api.post("/payments/checkout", {
                job_id: job.id, origin_url: window.location.origin,
            });
            window.location.href = data.url;
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail) || "Checkout failed");
        }
    };

    return (
        <div data-testid="jobs-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Work Orders</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">All Jobs</h1>
                </div>
                <button
                    onClick={() => { setEditing(null); setOpen(true); }}
                    data-testid="open-create-job-button"
                    className="bg-[#DC2626] text-white px-5 py-2.5 font-semibold hover:bg-[#B91C1C] flex items-center gap-2 transition-colors"
                >
                    <Plus weight="bold" /> New Work Order
                </button>
            </div>

            <div className="flex gap-2 border-b border-slate-200 overflow-x-auto">
                {["all", ...STATUS].map((s) => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        data-testid={`filter-${s}-button`}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap capitalize ${
                            filter === s
                                ? "border-[#DC2626] text-slate-900"
                                : "border-transparent text-slate-500 hover:text-slate-900"
                        }`}
                    >
                        {s.replace("_"," ")}
                        <span className="ml-2 text-xs text-slate-400">
                            {s === "all" ? jobs.length : jobs.filter((j) => j.status === s).length}
                        </span>
                    </button>
                ))}
            </div>

            <div className="border border-slate-200 overflow-x-auto">
                <table className="w-full text-sm" data-testid="jobs-table">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr className="text-left">
                            <th className="px-4 py-3 font-semibold">Job</th>
                            <th className="px-4 py-3 font-semibold">Customer</th>
                            <th className="px-4 py-3 font-semibold">Tech</th>
                            <th className="px-4 py-3 font-semibold">Scheduled</th>
                            <th className="px-4 py-3 font-semibold">Status</th>
                            <th className="px-4 py-3 font-semibold text-right">Price</th>
                            <th className="px-4 py-3 font-semibold text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {loading && (<tr><td colSpan={7} className="p-8 text-center text-slate-500">Loading...</td></tr>)}
                        {!loading && filtered.length === 0 && (
                            <tr><td colSpan={7} className="p-12 text-center text-slate-500">No jobs match this filter.</td></tr>
                        )}
                        {filtered.map((j) => (
                            <tr key={j.id} className="hover:bg-slate-50">
                                <td className="px-4 py-3">
                                    <Link to={`/app/jobs/${j.id}`} className="font-medium hover:underline" data-testid={`job-title-${j.id}`}>{j.title}</Link>
                                    <div className="text-xs text-slate-500">{j.job_type}</div>
                                </td>
                                <td className="px-4 py-3">
                                    <div>{j.customer_name || "—"}</div>
                                    <div className="text-xs text-slate-500">{j.customer_phone}</div>
                                </td>
                                <td className="px-4 py-3 text-slate-600">
                                    {team.find((t) => t.id === j.assigned_to)?.name || <span className="text-slate-400">Unassigned</span>}
                                </td>
                                <td className="px-4 py-3 text-slate-600">
                                    {j.scheduled_at ? new Date(j.scheduled_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—"}
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`text-xs px-2 py-1 border ${STATUS_COLORS[j.status]}`}>{j.status.replace("_"," ")}</span>
                                </td>
                                <td className="px-4 py-3 text-right font-mono">${(j.price || 0).toFixed(0)}</td>
                                <td className="px-4 py-3 text-right">
                                    <div className="flex items-center justify-end gap-2">
                                        {!j.paid && j.price > 0 && (
                                            <button
                                                onClick={() => pay(j)}
                                                data-testid={`pay-job-button-${j.id}`}
                                                className="text-xs flex items-center gap-1 px-2 py-1 border border-emerald-500 text-emerald-700 hover:bg-emerald-50"
                                            >
                                                <CreditCard size={12} /> Charge
                                            </button>
                                        )}
                                        {j.paid && (<span className="text-xs text-emerald-600 font-semibold">Paid</span>)}
                                        <button
                                            onClick={() => { setEditing(j); setOpen(true); }}
                                            data-testid={`edit-job-button-${j.id}`}
                                            className="text-xs px-2 py-1 border border-slate-300 hover:bg-slate-50"
                                        >Edit</button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {open && (
                <JobModal
                    onClose={() => setOpen(false)}
                    onSaved={() => { setOpen(false); load(); }}
                    team={team}
                    initial={editing}
                />
            )}
        </div>
    );
}

function JobModal({ onClose, onSaved, team, initial }) {
    const [form, setForm] = useState(initial || {
        title: "", description: "", customer_name: "", customer_phone: "",
        address: "", job_type: "HVAC", assigned_to: "",
        scheduled_at: "", duration_min: 60, price: 0, status: "unscheduled",
    });
    const [saving, setSaving] = useState(false);
    const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload = {
                ...form,
                price: parseFloat(form.price) || 0,
                duration_min: parseInt(form.duration_min) || 60,
                assigned_to: form.assigned_to || null,
                scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : null,
            };
            if (initial) await api.patch(`/jobs/${initial.id}`, payload);
            else await api.post("/jobs", payload);
            toast.success(initial ? "Job updated" : "Job created");
            onSaved();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail) || "Save failed");
        } finally {
            setSaving(false);
        }
    };

    const localDt = form.scheduled_at
        ? new Date(form.scheduled_at).toISOString().slice(0, 16)
        : "";

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-2xl max-h-[90vh] overflow-y-auto border border-slate-300" onClick={(e) => e.stopPropagation()} data-testid="job-modal">
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                    <h2 className="font-display text-2xl font-extrabold tracking-tighter">{initial ? "Edit Job" : "New Work Order"}</h2>
                    <button onClick={onClose} data-testid="close-job-modal-button" className="p-1"><X size={20} /></button>
                </div>
                <form onSubmit={submit} className="p-6 space-y-4">
                    <div>
                        <label className="text-xs font-medium">Title</label>
                        <input required value={form.title} onChange={update("title")} data-testid="job-title-input"
                            className="mt-1 w-full border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs font-medium">Customer</label>
                            <input value={form.customer_name} onChange={update("customer_name")} data-testid="job-customer-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                        </div>
                        <div>
                            <label className="text-xs font-medium">Phone</label>
                            <input value={form.customer_phone} onChange={update("customer_phone")}
                                className="mt-1 w-full border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-medium">Address</label>
                        <input value={form.address} onChange={update("address")}
                            className="mt-1 w-full border border-slate-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                        <div>
                            <label className="text-xs font-medium">Type</label>
                            <select value={form.job_type} onChange={update("job_type")} className="mt-1 w-full border border-slate-300 px-3 py-2 bg-white">
                                {["HVAC","Plumbing","Electrical","Garage Doors","Roofing","Appliance Repair","Other"].map(t => <option key={t}>{t}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="text-xs font-medium">Assign to</label>
                            <select value={form.assigned_to || ""} onChange={update("assigned_to")} data-testid="job-assign-select"
                                className="mt-1 w-full border border-slate-300 px-3 py-2 bg-white">
                                <option value="">Unassigned</option>
                                {team.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.role})</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="text-xs font-medium">Status</label>
                            <select value={form.status} onChange={update("status")} className="mt-1 w-full border border-slate-300 px-3 py-2 bg-white capitalize">
                                {STATUS.map(s => <option key={s} value={s}>{s.replace("_"," ")}</option>)}
                            </select>
                        </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                        <div>
                            <label className="text-xs font-medium">Scheduled</label>
                            <input type="datetime-local" value={localDt}
                                onChange={(e) => setForm((f) => ({ ...f, scheduled_at: e.target.value ? new Date(e.target.value).toISOString() : "" }))}
                                data-testid="job-schedule-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2" />
                        </div>
                        <div>
                            <label className="text-xs font-medium">Duration (min)</label>
                            <input type="number" min={15} value={form.duration_min} onChange={update("duration_min")}
                                className="mt-1 w-full border border-slate-300 px-3 py-2" />
                        </div>
                        <div>
                            <label className="text-xs font-medium">Price ($)</label>
                            <input type="number" step="0.01" min={0} value={form.price} onChange={update("price")} data-testid="job-price-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2" />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs font-medium">Notes</label>
                        <textarea value={form.description} onChange={update("description")} rows={3}
                            className="mt-1 w-full border border-slate-300 px-3 py-2" />
                    </div>
                    <div className="flex justify-end gap-3 pt-2">
                        <button type="button" onClick={onClose} className="px-4 py-2 border border-slate-300 hover:bg-slate-50">Cancel</button>
                        <button type="submit" disabled={saving} data-testid="save-job-button"
                            className="px-5 py-2 bg-[#1D4ED8] text-white font-semibold hover:bg-[#1E40AF] disabled:opacity-60">
                            {saving ? "Saving..." : (initial ? "Update" : "Create")}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
