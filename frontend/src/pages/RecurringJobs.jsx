import { useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import {
    ArrowsClockwise, Plus, Play, Trash, Pause,
} from "@phosphor-icons/react";

const CADENCES = [
    { value: "weekly", label: "Weekly (every 7d)" },
    { value: "biweekly", label: "Bi-weekly (every 14d)" },
    { value: "monthly", label: "Monthly (every 30d)" },
    { value: "quarterly", label: "Quarterly (every 90d)" },
    { value: "annually", label: "Annually (every 365d)" },
    { value: "custom", label: "Custom day interval" },
];

const empty = {
    title: "", description: "",
    customer_name: "", customer_phone: "", customer_email: "", address: "",
    job_type: "HVAC", price: 0, duration_min: 60,
    cadence: "monthly", interval_days: 30, active: true,
};

export default function RecurringJobs() {
    const { user } = useAuth();
    const [rows, setRows] = useState([]);
    const [creating, setCreating] = useState(false);
    const [form, setForm] = useState(empty);

    const canManage = ["owner", "dispatcher", "office_manager"].includes(user?.role);

    const load = () => api.get("/recurring-jobs").then((r) => setRows(r.data));
    useEffect(() => { load(); }, []);

    const submit = async (e) => {
        e.preventDefault();
        try {
            const payload = { ...form, price: Number(form.price), duration_min: Number(form.duration_min) };
            if (payload.cadence === "custom") payload.interval_days = Number(payload.interval_days);
            else delete payload.interval_days;
            await api.post("/recurring-jobs", payload);
            toast.success("Recurring plan created");
            setCreating(false); setForm(empty); load();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Could not save");
        }
    };

    const runNow = async (id) => {
        try {
            await api.post(`/recurring-jobs/${id}/run`);
            toast.success("Next occurrence created");
            load();
        } catch { toast.error("Could not run"); }
    };

    const toggleActive = async (r) => {
        try {
            await api.patch(`/recurring-jobs/${r.id}`, { active: !r.active });
            load();
        } catch { toast.error("Could not update"); }
    };

    const remove = async (id) => {
        if (!confirm("Delete this recurring plan?")) return;
        try {
            await api.delete(`/recurring-jobs/${id}`);
            toast.success("Deleted");
            load();
        } catch { toast.error("Could not delete"); }
    };

    return (
        <div data-testid="recurring-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Maintenance plans</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Recurring Jobs</h1>
                    <p className="text-sm text-slate-500 mt-2">
                        Templates that auto-materialize new work orders on a cadence. Great for HVAC tune-ups, filter swaps, drain flushes.
                    </p>
                </div>
                {canManage && (
                    <button onClick={() => setCreating((v) => !v)} data-testid="new-recurring-button"
                        className="h-10 px-4 bg-[#1D4ED8] hover:bg-blue-700 text-white font-semibold flex items-center gap-2">
                        <Plus weight="bold" size={14} /> New recurring
                    </button>
                )}
            </div>

            {creating && (
                <form onSubmit={submit} data-testid="recurring-form"
                    className="border border-slate-200 p-5 grid sm:grid-cols-2 gap-3 bg-white">
                    <Field label="Title" required value={form.title} onChange={(v) => setForm({ ...form, title: v })} testid="rec-title" />
                    <Field label="Customer name" value={form.customer_name} onChange={(v) => setForm({ ...form, customer_name: v })} testid="rec-customer" />
                    <Field label="Customer phone" value={form.customer_phone} onChange={(v) => setForm({ ...form, customer_phone: v })} testid="rec-phone" />
                    <Field label="Service address (include ZIP)" value={form.address} onChange={(v) => setForm({ ...form, address: v })} testid="rec-address" />
                    <Field label="Price" type="number" step="0.01" value={form.price} onChange={(v) => setForm({ ...form, price: v })} testid="rec-price" />
                    <Field label="Duration (min)" type="number" value={form.duration_min} onChange={(v) => setForm({ ...form, duration_min: v })} testid="rec-duration" />
                    <div>
                        <label className="text-xs font-medium">Cadence</label>
                        <select value={form.cadence} onChange={(e) => setForm({ ...form, cadence: e.target.value })}
                            data-testid="rec-cadence"
                            className="mt-1 w-full border border-slate-300 px-3 py-2.5 bg-white">
                            {CADENCES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                        </select>
                    </div>
                    {form.cadence === "custom" && (
                        <Field label="Repeat every N days" type="number" min="1" required
                            value={form.interval_days} onChange={(v) => setForm({ ...form, interval_days: v })}
                            testid="rec-interval" />
                    )}
                    <div className="sm:col-span-2 flex justify-end gap-2">
                        <button type="button" onClick={() => { setCreating(false); setForm(empty); }}
                            className="px-4 py-2 border border-slate-300 hover:bg-slate-50 font-medium">Cancel</button>
                        <button type="submit" data-testid="rec-submit"
                            className="px-4 py-2 bg-[#1D4ED8] text-white font-semibold hover:opacity-90">
                            Save recurring plan
                        </button>
                    </div>
                </form>
            )}

            {rows.length === 0 ? (
                <div className="border border-dashed border-slate-300 p-10 text-center text-slate-500">
                    <ArrowsClockwise size={28} className="mx-auto mb-3" weight="duotone" />
                    No recurring plans yet. Create one to schedule maintenance work automatically.
                </div>
            ) : (
                <div className="border border-slate-200 overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                            <tr>
                                <th className="text-left px-4 py-3">Title</th>
                                <th className="text-left px-4 py-3">Customer</th>
                                <th className="text-left px-4 py-3">Cadence</th>
                                <th className="text-left px-4 py-3">Next run</th>
                                <th className="text-left px-4 py-3">Status</th>
                                <th className="text-right px-4 py-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((r) => (
                                <tr key={r.id} data-testid={`recurring-row-${r.id}`} className="border-t border-slate-200">
                                    <td className="px-4 py-3 font-semibold">{r.title}</td>
                                    <td className="px-4 py-3 text-slate-600">{r.customer_name || "—"}</td>
                                    <td className="px-4 py-3 text-slate-600">
                                        {r.cadence}{r.cadence === "custom" && ` (${r.interval_days}d)`}
                                    </td>
                                    <td className="px-4 py-3 text-slate-600 font-mono text-xs">
                                        {r.next_run_at ? new Date(r.next_run_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—"}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`text-[10px] px-2 py-0.5 font-semibold uppercase tracking-wider ${r.active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                                            {r.active ? "Active" : "Paused"}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <div className="inline-flex gap-1">
                                            <button onClick={() => runNow(r.id)} data-testid={`recurring-run-${r.id}`}
                                                title="Run now" className="h-8 w-8 border border-slate-300 hover:bg-slate-50 flex items-center justify-center">
                                                <Play size={14} />
                                            </button>
                                            {canManage && (
                                                <>
                                                    <button onClick={() => toggleActive(r)} data-testid={`recurring-toggle-${r.id}`}
                                                        title={r.active ? "Pause" : "Resume"} className="h-8 w-8 border border-slate-300 hover:bg-slate-50 flex items-center justify-center">
                                                        {r.active ? <Pause size={14} /> : <Play size={14} weight="fill" />}
                                                    </button>
                                                    <button onClick={() => remove(r.id)} data-testid={`recurring-delete-${r.id}`}
                                                        title="Delete" className="h-8 w-8 border border-slate-300 hover:bg-red-50 hover:text-[#DC2626] flex items-center justify-center">
                                                        <Trash size={14} />
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

function Field({ label, testid, type = "text", value, onChange, required, step, min }) {
    return (
        <div>
            <label className="text-xs font-medium">{label}{required && " *"}</label>
            <input type={type} value={value} onChange={(e) => onChange(e.target.value)} required={required} step={step} min={min}
                data-testid={testid}
                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
        </div>
    );
}
