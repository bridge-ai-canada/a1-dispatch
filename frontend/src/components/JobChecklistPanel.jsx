import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    ListChecks, Plus, Check, Trash, PencilSimple, FloppyDisk, X,
} from "@phosphor-icons/react";

/**
 * Per-job checklist panel.
 * - Lists current checklist on the job
 * - Apply template (when empty)
 * - Add/edit/delete items locally to this job (does NOT touch master template)
 * - Toggle complete/incomplete
 */
export default function JobChecklistPanel({ job, onChange }) {
    const items = job.checklist || [];
    const [templates, setTemplates] = useState([]);
    const [loadingTpls, setLoadingTpls] = useState(false);
    const [selectedTpl, setSelectedTpl] = useState("");
    const [newItemTitle, setNewItemTitle] = useState("");
    const [newItemRequired, setNewItemRequired] = useState(false);
    const [editing, setEditing] = useState(null); // item.id

    useEffect(() => {
        if (items.length > 0) return;
        setLoadingTpls(true);
        api.get("/checklist-templates")
            .then(({ data }) => setTemplates(data))
            .catch(() => {})
            .finally(() => setLoadingTpls(false));
    }, [items.length]);

    const refresh = (data) => {
        if (data?.checklist && onChange) onChange({ ...job, checklist: data.checklist });
    };

    const apply = async () => {
        if (!selectedTpl) return toast.error("Pick a template");
        try {
            const { data } = await api.post(`/jobs/${job.id}/checklist/apply`, { template_id: selectedTpl });
            refresh(data);
            toast.success("Checklist applied");
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const toggle = async (item) => {
        try {
            const { data } = await api.post(`/jobs/${job.id}/checklist/toggle`, {
                item_id: item.id, completed: !item.completed,
            });
            refresh(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const addItem = async () => {
        const t = newItemTitle.trim();
        if (!t) return;
        try {
            const { data } = await api.post(`/jobs/${job.id}/checklist/items`, {
                title: t, required: newItemRequired,
            });
            refresh(data);
            setNewItemTitle("");
            setNewItemRequired(false);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const saveEdit = async (item, patch) => {
        try {
            const { data } = await api.put(`/jobs/${job.id}/checklist/items/${item.id}`, patch);
            refresh(data);
            setEditing(null);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const removeItem = async (item) => {
        if (!window.confirm("Remove this item from this job's checklist?")) return;
        try {
            const { data } = await api.delete(`/jobs/${job.id}/checklist/items/${item.id}`);
            refresh(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const clearAll = async () => {
        if (!window.confirm("Clear all checklist items from this job?")) return;
        try {
            const { data } = await api.delete(`/jobs/${job.id}/checklist`);
            refresh(data);
            toast.success("Checklist cleared");
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const completed = items.filter((i) => i.completed).length;
    const total = items.length;
    const requiredRemaining = items.filter((i) => i.required && !i.completed).length;
    const pct = total ? Math.round((completed / total) * 100) : 0;

    return (
        <section className="border border-slate-200" data-testid="job-checklist-panel">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap">
                <div className="overline flex items-center gap-1.5">
                    <ListChecks size={14}/> Checklist {total > 0 && <span className="text-slate-400">· {completed}/{total}</span>}
                </div>
                {total > 0 && (
                    <div className="flex items-center gap-2">
                        {requiredRemaining > 0 && (
                            <span className="text-[10px] px-2 py-0.5 bg-rose-50 text-rose-700 font-bold uppercase tracking-wider rounded">
                                {requiredRemaining} required left
                            </span>
                        )}
                        {pct === 100 && (
                            <span className="text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-700 font-bold uppercase tracking-wider rounded">
                                Complete
                            </span>
                        )}
                        <button onClick={clearAll} className="text-xs text-slate-400 hover:text-rose-600" data-testid="checklist-clear-button">
                            Clear
                        </button>
                    </div>
                )}
            </div>

            {total === 0 ? (
                <div className="p-5 space-y-3">
                    <p className="text-sm text-slate-500">No checklist on this job yet.</p>
                    {templates.length > 0 ? (
                        <div className="flex flex-col sm:flex-row gap-2">
                            <select
                                value={selectedTpl}
                                onChange={(e) => setSelectedTpl(e.target.value)}
                                className="flex-1 px-3 py-2 border border-slate-300 rounded text-sm bg-white"
                                data-testid="checklist-template-select"
                            >
                                <option value="">— Pick a template —</option>
                                {templates.map((t) => (
                                    <option key={t.id} value={t.id}>
                                        {t.name}{t.job_type ? ` (${t.job_type})` : ""} · {(t.items || []).length} items
                                    </option>
                                ))}
                            </select>
                            <button
                                onClick={apply}
                                disabled={!selectedTpl}
                                className="px-4 py-2 bg-[#1D4ED8] hover:bg-[#1E40AF] text-white text-sm font-semibold rounded disabled:opacity-50"
                                data-testid="checklist-apply-button"
                            >
                                Apply
                            </button>
                        </div>
                    ) : !loadingTpls ? (
                        <p className="text-xs text-slate-400">
                            No templates yet. <a href="/app/checklists" className="text-[#1D4ED8] font-semibold hover:underline">Create one →</a>
                        </p>
                    ) : null}
                </div>
            ) : (
                <>
                    <div className="h-1.5 bg-slate-100 overflow-hidden">
                        <div className="h-full bg-emerald-500 transition-all" style={{ width: `${pct}%` }}/>
                    </div>
                    <ul className="divide-y divide-slate-100">
                        {items.map((it) => (
                            <li
                                key={it.id}
                                className="flex items-center gap-3 px-5 py-2.5 group hover:bg-slate-50/50"
                                data-testid={`checklist-row-${it.id}`}
                            >
                                <button
                                    onClick={() => toggle(it)}
                                    className={`h-5 w-5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                                        it.completed ? "bg-emerald-500 border-emerald-500 text-white" : "bg-white border-slate-300 hover:border-emerald-500"
                                    }`}
                                    data-testid={`checklist-toggle-${it.id}`}
                                    aria-label={it.completed ? "Mark incomplete" : "Mark complete"}
                                >
                                    {it.completed && <Check size={13} weight="bold"/>}
                                </button>
                                {editing === it.id ? (
                                    <InlineEditor item={it} onSave={(patch) => saveEdit(it, patch)} onCancel={() => setEditing(null)}/>
                                ) : (
                                    <>
                                        <span className={`flex-1 text-sm ${it.completed ? "line-through text-slate-400" : "text-slate-800"}`}>
                                            {it.title}
                                            {it.required && <span className="text-[9px] uppercase tracking-wider text-rose-600 font-bold ml-2">req</span>}
                                        </span>
                                        <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                                            <button onClick={() => setEditing(it.id)} className="p-1 text-slate-400 hover:text-[#1D4ED8]" data-testid={`checklist-edit-row-${it.id}`}>
                                                <PencilSimple size={13}/>
                                            </button>
                                            <button onClick={() => removeItem(it)} className="p-1 text-slate-400 hover:text-[#DC2626]" data-testid={`checklist-remove-row-${it.id}`}>
                                                <Trash size={13}/>
                                            </button>
                                        </div>
                                    </>
                                )}
                            </li>
                        ))}
                    </ul>
                </>
            )}

            {/* Add item row — always visible once items exist or when no templates available */}
            {(total > 0 || templates.length === 0) && (
                <div className="px-5 py-3 border-t border-slate-200 flex items-center gap-2">
                    <input
                        value={newItemTitle}
                        onChange={(e) => setNewItemTitle(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && addItem()}
                        placeholder="Add a checklist item…"
                        className="flex-1 px-3 py-1.5 border border-slate-300 rounded text-sm"
                        data-testid="checklist-new-item-input"
                    />
                    <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1 cursor-pointer">
                        <input type="checkbox" checked={newItemRequired} onChange={(e) => setNewItemRequired(e.target.checked)} />
                        Req
                    </label>
                    <button
                        onClick={addItem}
                        disabled={!newItemTitle.trim()}
                        className="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-bold rounded inline-flex items-center gap-1"
                        data-testid="checklist-add-row-button"
                    >
                        <Plus size={12} weight="bold"/> Add
                    </button>
                </div>
            )}
        </section>
    );
}

function InlineEditor({ item, onSave, onCancel }) {
    const [title, setTitle] = useState(item.title);
    const [required, setRequired] = useState(!!item.required);

    const save = () => {
        const t = title.trim();
        if (!t) return;
        onSave({ title: t, required });
    };

    return (
        <div className="flex-1 flex items-center gap-2">
            <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === "Enter") save();
                    if (e.key === "Escape") onCancel();
                }}
                autoFocus
                className="flex-1 px-2 py-1 border border-slate-300 rounded text-sm"
                data-testid={`checklist-edit-input-${item.id}`}
            />
            <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
                Req
            </label>
            <button onClick={save} className="p-1 text-emerald-600 hover:text-emerald-700" data-testid={`checklist-save-edit-${item.id}`}>
                <FloppyDisk size={14}/>
            </button>
            <button onClick={onCancel} className="p-1 text-slate-400 hover:text-slate-700" data-testid={`checklist-cancel-edit-${item.id}`}>
                <X size={14}/>
            </button>
        </div>
    );
}
