import { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Funnel } from "@phosphor-icons/react";

const COLUMNS = [
    { key: "new_lead",               label: "New leads",          accent: "#0EA5E9" },
    { key: "contacted",              label: "Contacted",          accent: "#0891B2" },
    { key: "qualified",              label: "Qualified",          accent: "#06B6D4" },
    { key: "quote_sent",             label: "Quote sent",         accent: "#8B5CF6" },
    { key: "won_bid",                label: "Won bids",           accent: "#7C3AED" },
    { key: "scheduled_installation", label: "Scheduled install",  accent: "#1D4ED8" },
    { key: "in_progress",            label: "In progress",        accent: "#D97706" },
    { key: "completed",              label: "Completed",          accent: "#16A34A" },
    { key: "unscheduled",            label: "Unscheduled",        accent: "#64748B" },
    { key: "on_hold",                label: "On hold",            accent: "#EA580C" },
    { key: "lost_bid",               label: "Lost bids",          accent: "#BE123C" },
    { key: "cancelled",              label: "Cancelled",          accent: "#DC2626" },
];

function fmtMoney(v) { return `$${(Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`; }
function shortDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function Pipeline() {
    const navigate = useNavigate();
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dragId, setDragId] = useState(null);
    const [dragOver, setDragOver] = useState(null);
    const [search, setSearch] = useState("");

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/jobs");
            setJobs(data);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setLoading(false); }
    }, []);
    useEffect(() => { load(); }, [load]);

    const cols = COLUMNS;

    const byCol = useMemo(() => {
        const s = (search || "").toLowerCase().trim();
        const filtered = !s ? jobs : jobs.filter((j) =>
            (j.title || "").toLowerCase().includes(s) ||
            (j.customer_name || "").toLowerCase().includes(s) ||
            (j.address || "").toLowerCase().includes(s)
        );
        const out = Object.fromEntries(cols.map((c) => [c.key, []]));
        for (const j of filtered) {
            const k = j.status === "scheduled" ? "scheduled_installation" : j.status;
            if (out[k]) out[k].push(j);
        }
        // sort each column by scheduled_at then created_at desc
        for (const k of Object.keys(out)) {
            out[k].sort((a, b) =>
                (a.scheduled_at || "").localeCompare(b.scheduled_at || "") ||
                (b.created_at || "").localeCompare(a.created_at || "")
            );
        }
        return out;
    }, [jobs, cols, search]);

    const totals = useMemo(() => {
        return Object.fromEntries(cols.map((c) => [
            c.key,
            (byCol[c.key] || []).reduce((s, j) => s + (Number(j.price) || 0), 0),
        ]));
    }, [byCol, cols]);

    const moveTo = async (jobId, nextStatus) => {
        const job = jobs.find((j) => j.id === jobId);
        if (!job) return;
        const prev = job.status;
        if (prev === nextStatus) return;
        // optimistic update
        setJobs((arr) => arr.map((j) => j.id === jobId ? { ...j, status: nextStatus } : j));
        try {
            await api.patch(`/jobs/${jobId}`, { status: nextStatus });
            toast.success(`Moved "${job.title}" → ${COLUMNS.find((c) => c.key === nextStatus)?.label || nextStatus}`);
        } catch (e) {
            setJobs((arr) => arr.map((j) => j.id === jobId ? { ...j, status: prev } : j));
            toast.error(formatApiError(e.response?.data?.detail) || "Move failed");
        }
    };

    return (
        <div className="space-y-5">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Pipeline</h1>
                    <p className="text-sm text-slate-500">Drag cards across columns to update job status.</p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative">
                        <input
                            type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                            placeholder="Search jobs…"
                            className="pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg w-56 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30"
                            data-testid="pipeline-search"
                        />
                        <Funnel size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                </div>
            </div>

            {/* Kanban */}
            {loading ? (
                <div className="text-sm text-slate-500">Loading…</div>
            ) : (
                <div className="overflow-x-auto pb-2 -mx-4 sm:-mx-6 px-4 sm:px-6" data-testid="pipeline-board">
                    <div className="flex gap-3 min-w-fit">
                        {cols.map((col) => (
                            <Column key={col.key} col={col}
                                items={byCol[col.key] || []}
                                total={totals[col.key]}
                                isOver={dragOver === col.key}
                                onDragOver={(e) => { e.preventDefault(); setDragOver(col.key); }}
                                onDragLeave={() => setDragOver(null)}
                                onDrop={() => { setDragOver(null); if (dragId) moveTo(dragId, col.key); setDragId(null); }}
                                onCardDragStart={setDragId}
                                onCardClick={(id) => navigate(`/app/jobs/${id}`)}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function Column({ col, items, total, isOver, onDragOver, onDragLeave, onDrop, onCardDragStart, onCardClick }) {
    return (
        <div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
            className={`w-80 shrink-0 rounded-2xl border-2 transition ${
                isOver ? "border-[#1D4ED8] bg-blue-50/60" : "border-slate-200 bg-slate-50"
            }`}
            data-testid={`pipeline-col-${col.key}`}>
            {/* Column header */}
            <div className="px-4 py-3 border-b border-slate-200 bg-white rounded-t-2xl"
                style={{ borderTopColor: col.accent, borderTopWidth: 3 }}>
                <div className="flex items-center justify-between">
                    <div className="font-extrabold text-slate-900 text-sm uppercase tracking-wider">
                        {col.label}
                    </div>
                    <div className="text-xs font-bold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                        {items.length}
                    </div>
                </div>
                <div className="text-xs font-bold text-slate-500 mt-1 font-mono">{fmtMoney(total)}</div>
            </div>
            {/* Cards */}
            <div className="p-2 space-y-2 min-h-32 max-h-[calc(100vh-18rem)] overflow-y-auto">
                {items.length === 0 ? (
                    <div className="text-center text-xs text-slate-400 py-8">Drag jobs here</div>
                ) : items.map((j) => (
                    <Card key={j.id} job={j} accent={col.accent}
                        onDragStart={() => onCardDragStart(j.id)}
                        onClick={() => onCardClick(j.id)} />
                ))}
            </div>
        </div>
    );
}

function Card({ job, accent, onDragStart, onClick }) {
    const isEmergency = job.priority === "emergency" || job.priority === "high";
    return (
        <div draggable
            onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; onDragStart(); }}
            onClick={onClick}
            className={`group bg-white rounded-xl p-3 cursor-pointer border transition hover:shadow-md hover:-translate-y-0.5 ${
                isEmergency ? "border-[#DC2626]" : "border-slate-200"
            }`}
            style={{ borderLeftWidth: 4, borderLeftColor: accent }}
            data-testid={`pipeline-card-${job.id}`}>
            <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-sm text-slate-900 line-clamp-2">{job.title}</div>
                {Number(job.price) > 0 && (
                    <div className="text-xs font-bold text-slate-700 shrink-0 font-mono">
                        {fmtMoney(job.price)}
                    </div>
                )}
            </div>
            {job.customer_name && (
                <div className="mt-1 text-xs text-slate-600 truncate">{job.customer_name}</div>
            )}
            {job.address && (
                <div className="text-xs text-slate-400 truncate">{job.address}</div>
            )}
            <div className="mt-2 flex items-center justify-between text-[10px] uppercase tracking-wider">
                {job.scheduled_at ? (
                    <span className="font-bold text-slate-500">{shortDate(job.scheduled_at)}</span>
                ) : <span/>}
                {isEmergency && (
                    <span className="bg-[#DC2626] text-white px-1.5 py-0.5 rounded font-bold">
                        {job.priority?.toUpperCase()}
                    </span>
                )}
            </div>
        </div>
    );
}
