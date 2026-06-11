import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    Plus, Trash, PencilSimple, X, FloppyDisk, Check, ListChecks, Copy,
} from "@phosphor-icons/react";

const JOB_TYPES = ["HVAC", "Plumbing", "Electrical", "Garage Doors", "Appliance Repair", "General", "Other"];

export default function Checklists() {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null); // template object or null
    const [showNew, setShowNew] = useState(false);

    const load = async () => {
        try {
            const { data } = await api.get("/checklist-templates");
            setTemplates(data);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally {
            setLoading(false);
        }
    };
    useEffect(() => { load(); }, []);

    const removeTemplate = async (id) => {
        if (!window.confirm("Delete this checklist template? Jobs that already applied it keep their copy.")) return;
        try {
            await api.delete(`/checklist-templates/${id}`);
            toast.success("Template deleted");
            load();
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        }
    };

    const duplicate = async (t) => {
        try {
            await api.post("/checklist-templates", {
                name: `${t.name} (copy)`,
                job_type: t.job_type || "",
                items: (t.items || []).map((i) => ({ title: i.title, required: !!i.required })),
            });
            toast.success("Template duplicated");
            load();
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        }
    };

    return (
        <div data-testid="checklists-page" className="space-y-6 max-w-6xl">
            <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
                <div>
                    <div className="overline">Quality Control</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
                        <ListChecks size={32}/> Checklist templates
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Standard operating procedures your techs follow on every job. Apply to any work order in one click.
                    </p>
                </div>
                <button
                    onClick={() => setShowNew(true)}
                    data-testid="new-checklist-button"
                    className="inline-flex items-center gap-2 bg-[#1D4ED8] hover:bg-[#1E40AF] text-white font-semibold px-4 py-2.5 rounded-lg shadow-sm"
                >
                    <Plus size={18} weight="bold"/> New checklist
                </button>
            </header>

            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : templates.length === 0 ? (
                <div className="text-center py-20 rounded-2xl border-2 border-dashed border-slate-200">
                    <ListChecks size={56} className="mx-auto text-slate-300"/>
                    <p className="mt-3 text-slate-600 font-semibold">No checklists yet</p>
                    <p className="text-sm text-slate-500 max-w-md mx-auto mt-1">
                        Build a standard run-through (e.g., &quot;AC Tune-up: 12 items&quot;) and reuse it on every job to lock in quality.
                    </p>
                    <button
                        onClick={() => setShowNew(true)}
                        className="mt-4 inline-flex items-center gap-1.5 bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-sm font-semibold px-4 py-2 rounded-lg"
                        data-testid="empty-new-checklist-button"
                    >
                        <Plus size={14}/> Create your first checklist
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {templates.map((t) => (
                        <div key={t.id} className="border border-slate-200 rounded-2xl p-5 bg-white hover:shadow-md transition-shadow" data-testid={`checklist-card-${t.id}`}>
                            <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                    {t.job_type && <div className="overline">{t.job_type}</div>}
                                    <div className="font-bold text-lg truncate">{t.name}</div>
                                </div>
                                <div className="flex items-center gap-1 shrink-0">
                                    <button onClick={() => duplicate(t)} title="Duplicate" data-testid={`checklist-duplicate-${t.id}`}
                                        className="p-1.5 text-slate-400 hover:text-slate-700">
                                        <Copy size={15}/>
                                    </button>
                                    <button onClick={() => setEditing(t)} title="Edit" data-testid={`checklist-edit-${t.id}`}
                                        className="p-1.5 text-slate-400 hover:text-[#1D4ED8]">
                                        <PencilSimple size={15}/>
                                    </button>
                                    <button onClick={() => removeTemplate(t.id)} title="Delete" data-testid={`checklist-delete-${t.id}`}
                                        className="p-1.5 text-slate-400 hover:text-[#DC2626]">
                                        <Trash size={15}/>
                                    </button>
                                </div>
                            </div>
                            <div className="mt-3 text-xs text-slate-500">
                                {(t.items || []).length} item{(t.items || []).length === 1 ? "" : "s"} · {" "}
                                {(t.items || []).filter((i) => i.required).length} required
                            </div>
                            <ul className="mt-3 space-y-1 max-h-44 overflow-y-auto">
                                {(t.items || []).slice(0, 8).map((i) => (
                                    <li key={i.id} className="text-sm text-slate-700 flex items-start gap-2">
                                        <Check size={13} className="mt-0.5 text-slate-300 shrink-0"/>
                                        <span className="truncate">{i.title}</span>
                                        {i.required && <span className="text-[9px] uppercase tracking-wider text-rose-600 font-bold ml-auto shrink-0">req</span>}
                                    </li>
                                ))}
                                {(t.items || []).length > 8 && (
                                    <li className="text-xs text-slate-400 pl-5">+{(t.items || []).length - 8} more…</li>
                                )}
                            </ul>
                        </div>
                    ))}
                </div>
            )}

            {(showNew || editing) && (
                <ChecklistEditor
                    template={editing}
                    onClose={() => { setShowNew(false); setEditing(null); }}
                    onSaved={() => { setShowNew(false); setEditing(null); load(); }}
                />
            )}
        </div>
    );
}

function ChecklistEditor({ template, onClose, onSaved }) {
    const isNew = !template;
    const [name, setName] = useState(template?.name || "");
    const [jobType, setJobType] = useState(template?.job_type || "");
    const [items, setItems] = useState(() =>
        (template?.items || []).map((i) => ({ ...i }))
    );
    const [saving, setSaving] = useState(false);

    const addItem = () => setItems((it) => [...it, { title: "", required: false }]);
    const removeItem = (idx) => setItems((it) => it.filter((_, i) => i !== idx));
    const updateItem = (idx, patch) =>
        setItems((it) => it.map((x, i) => (i === idx ? { ...x, ...patch } : x)));

    const save = async () => {
        const cleaned = items.map((i) => ({ title: (i.title || "").trim(), required: !!i.required }))
            .filter((i) => i.title);
        if (!name.trim()) return toast.error("Name required");
        if (cleaned.length === 0) return toast.error("Add at least one item");
        setSaving(true);
        try {
            const body = { name: name.trim(), job_type: jobType, items: cleaned };
            if (isNew) {
                await api.post("/checklist-templates", body);
                toast.success("Template created");
            } else {
                await api.put(`/checklist-templates/${template.id}`, body);
                toast.success("Template updated");
            }
            onSaved();
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-end sm:items-center justify-center p-2 sm:p-4" onClick={onClose}>
            <div
                className="bg-white rounded-3xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()}
                data-testid="checklist-editor-modal"
            >
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="text-xl font-extrabold tracking-tight">
                            {isNew ? "New checklist" : "Edit checklist"}
                        </h3>
                        <p className="text-xs text-slate-500 mt-0.5">Define a reusable run-through for a job type.</p>
                    </div>
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700" data-testid="checklist-editor-close">
                        <X size={20}/>
                    </button>
                </div>

                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Name</span>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="AC Tune-up (Summer)"
                            className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                            data-testid="checklist-name-input"
                        />
                    </label>
                    <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Job type</span>
                        <select
                            value={jobType}
                            onChange={(e) => setJobType(e.target.value)}
                            className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white"
                            data-testid="checklist-job-type"
                        >
                            <option value="">— Any job type —</option>
                            {JOB_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                        </select>
                    </label>
                </div>

                <div className="mt-5">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Items</span>
                        <button onClick={addItem}
                            className="text-xs text-[#1D4ED8] font-semibold hover:underline inline-flex items-center gap-1"
                            data-testid="checklist-add-item">
                            <Plus size={12} weight="bold"/> Add item
                        </button>
                    </div>
                    {items.length === 0 && (
                        <div className="text-center py-6 text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg">
                            No items yet. Click <strong>Add item</strong> to begin.
                        </div>
                    )}
                    <ul className="space-y-2">
                        {items.map((it, idx) => (
                            <li key={idx} className="flex items-center gap-2" data-testid={`checklist-item-row-${idx}`}>
                                <span className="text-xs text-slate-400 w-5 text-right">{idx + 1}.</span>
                                <input
                                    value={it.title}
                                    onChange={(e) => updateItem(idx, { title: e.target.value })}
                                    placeholder="Check refrigerant pressure"
                                    className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                    data-testid={`checklist-item-title-${idx}`}
                                />
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={!!it.required}
                                        onChange={(e) => updateItem(idx, { required: e.target.checked })}
                                        data-testid={`checklist-item-required-${idx}`}
                                    />
                                    Required
                                </label>
                                <button onClick={() => removeItem(idx)} className="p-1.5 text-slate-400 hover:text-[#DC2626]" data-testid={`checklist-item-delete-${idx}`}>
                                    <Trash size={15}/>
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>

                <div className="mt-6 flex gap-2">
                    <button onClick={onClose} className="flex-1 py-2.5 border border-slate-300 rounded-lg text-sm font-semibold hover:bg-slate-50">
                        Cancel
                    </button>
                    <button
                        onClick={save}
                        disabled={saving}
                        className="flex-1 py-2.5 bg-[#1D4ED8] hover:bg-[#1E40AF] disabled:opacity-60 text-white text-sm font-bold rounded-lg inline-flex items-center justify-center gap-1.5"
                        data-testid="checklist-save-button"
                    >
                        <FloppyDisk size={14}/> {saving ? "Saving…" : isNew ? "Create" : "Save changes"}
                    </button>
                </div>
            </div>
        </div>
    );
}
