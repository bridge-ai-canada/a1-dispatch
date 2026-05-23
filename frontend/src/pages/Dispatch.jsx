import { useEffect, useMemo, useState, useRef } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { useDispatchSocket } from "../lib/dispatchSocket";
import {
    CalendarBlank, MapTrifold, Lightning, ListBullets, CaretLeft, CaretRight,
    CircleNotch, Plus, Phone, MapPin, Wrench, Clock,
} from "@phosphor-icons/react";
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from "react-leaflet";
import L from "leaflet";
import "./Dispatch.css";
import AIDispatcherPanel from "../components/AIDispatcherPanel";

// Fix Leaflet default icon URLs (won't load through webpack otherwise)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const HOUR_START = 7;
const HOUR_END = 20;
const ROW_PX = 56; // px per hour-row in day view

const VIEWS = [
    { id: "day",   label: "Day",   icon: ListBullets },
    { id: "week",  label: "Week",  icon: CalendarBlank },
    { id: "month", label: "Month", icon: CalendarBlank },
    { id: "map",   label: "Map",   icon: MapTrifold },
];

const PRIORITY_RING = {
    emergency: "ring-2 ring-[#DC2626]",
    high:      "ring-1 ring-amber-500",
    normal:    "",
    low:       "",
};

const STATUS_BG = {
    unscheduled: "bg-slate-100 text-slate-700",
    won_bid:     "bg-violet-50 text-violet-700",
    lost_bid:    "bg-rose-50 text-rose-700",
    on_hold:     "bg-orange-50 text-orange-700",
    scheduled_installation: "bg-blue-50 text-[#1D4ED8]",
    scheduled:   "bg-blue-50 text-[#1D4ED8]",
    in_progress: "bg-amber-50 text-amber-700",
    completed:   "bg-emerald-50 text-emerald-700",
    cancelled:   "bg-red-50 text-[#DC2626]",
};

const TYPE_COLOR = {
    HVAC: "#1D4ED8",
    Plumbing: "#0EA5E9",
    Electrical: "#D97706",
    "Garage Doors": "#7C3AED",
    Roofing: "#65A30D",
    "Appliance Repair": "#0891B2",
    Other: "#64748B",
};

const TECH_STATUS_BADGE = {
    available: { color: "#16A34A", label: "Available" },
    on_route:  { color: "#1D4ED8", label: "On route" },
    on_site:   { color: "#D97706", label: "On site" },
    break:     { color: "#94A3B8", label: "Break" },
    off_duty:  { color: "#475569", label: "Off duty" },
};

function dateKey(d)   { return new Date(d).toISOString().slice(0, 10); }
function startOfWeek(d) {
    const dt = new Date(d);
    const day = dt.getDay();
    dt.setDate(dt.getDate() - day);
    dt.setHours(0, 0, 0, 0);
    return dt;
}
function startOfMonth(d) { const dt = new Date(d); dt.setDate(1); dt.setHours(0,0,0,0); return dt; }
function addDays(d, n) { const dt = new Date(d); dt.setDate(dt.getDate() + n); return dt; }
function fmtMonthYear(d) { return d.toLocaleString([], { month: "long", year: "numeric" }); }
function fmtTime(iso) { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

// Naive geocode fallback: extract street # + zip; if no lat/lng exists, return null.
// Real geocoding is a roadmap item (Mapbox/Google). For now we plot only items with lat/lng.

export default function Dispatch() {
    const [jobs, setJobs] = useState([]);
    const [team, setTeam] = useState([]);
    const [locations, setLocations] = useState([]); // [{id,name,role,tech_status,last_location?:{lat,lng,ts}}]
    const [view, setView] = useState("day");
    const [anchor, setAnchor] = useState(() => { const d = new Date(); d.setHours(0,0,0,0); return d; });
    const [loading, setLoading] = useState(true);
    const [filterEmergency, setFilterEmergency] = useState(false);
    const [draggingId, setDraggingId] = useState(null);
    const [dragOver, setDragOver] = useState(null);

    const load = async () => {
        try {
            const [j, t, l] = await Promise.all([
                api.get("/jobs"),
                api.get("/team"),
                api.get("/team/locations"),
            ]);
            setJobs(j.data); setTeam(t.data); setLocations(l.data);
        } finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []);

    // Realtime
    const { connected } = useDispatchSocket((msg) => {
        if (msg.type === "job.created") {
            setJobs((prev) => [msg.data, ...prev.filter((j) => j.id !== msg.data.id)]);
            if (msg.data.priority === "emergency") toast("🚨 Emergency job created", { description: msg.data.title });
        } else if (msg.type === "job.updated") {
            setJobs((prev) => prev.map((j) => (j.id === msg.data.id ? { ...j, ...msg.data } : j)));
        } else if (msg.type === "job.geocoded") {
            setJobs((prev) => prev.map((j) =>
                j.id === msg.data.job_id ? { ...j, location: msg.data.location } : j
            ));
        } else if (msg.type === "user.status") {
            setLocations((prev) => prev.map((u) =>
                u.id === msg.data.user_id ? { ...u, tech_status: msg.data.status, tech_status_at: msg.data.ts } : u
            ));
        } else if (msg.type === "user.location") {
            setLocations((prev) => prev.map((u) =>
                u.id === msg.data.user_id ? { ...u, last_location: { lat: msg.data.lat, lng: msg.data.lng, ts: msg.data.ts } } : u
            ));
        }
    });

    const techs = team.filter((t) => t.role === "technician");
    const filteredJobs = filterEmergency ? jobs.filter((j) => j.priority === "emergency") : jobs;
    const unassigned = filteredJobs.filter((j) => !j.assigned_to);
    const emergencyCount = jobs.filter((j) => j.priority === "emergency" && j.status !== "completed" && j.status !== "cancelled").length;

    // ----- Drag / drop ----- //
    const dropOnSlot = async (techId, datetimeIso) => {
        if (!draggingId) return;
        const job = jobs.find((j) => j.id === draggingId);
        if (!job) return;
        const prev = jobs;
        // Optimistic update
        setJobs((p) => p.map((j) => j.id === draggingId
            ? { ...j, assigned_to: techId, scheduled_at: datetimeIso, status: j.status === "unscheduled" ? "scheduled_installation" : j.status }
            : j));
        try {
            await api.patch(`/jobs/${draggingId}`, {
                assigned_to: techId,
                scheduled_at: datetimeIso,
                ...(job.status === "unscheduled" ? { status: "scheduled_installation" } : {}),
            });
        } catch (e) {
            toast.error(e.response?.data?.detail || "Reassign failed");
            setJobs(prev);
        } finally {
            setDraggingId(null); setDragOver(null);
        }
    };

    const optimize = async (techId) => {
        const day = dateKey(anchor);
        try {
            const { data } = await api.post("/jobs/optimize-route", { technician_id: techId, date: day, gap_min: 30 });
            toast.success(`Optimized ${data.reordered} stops for today`);
            load();
        } catch (e) { toast.error(e.response?.data?.detail || "Optimize failed"); }
    };

    if (loading) return <Loader />;

    return (
        <div data-testid="dispatch-page" className="space-y-4">
            <Header
                view={view} setView={setView}
                anchor={anchor} setAnchor={setAnchor}
                connected={connected}
                emergencyCount={emergencyCount}
                filterEmergency={filterEmergency} setFilterEmergency={setFilterEmergency}
                onRefresh={load}
            />

            <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr_280px] gap-4">
                {/* LEFT: technicians */}
                <TechRail techs={techs} locations={locations} onOptimize={optimize} />

                {/* CENTER: calendar / map */}
                <main className="bg-white border border-slate-200 min-h-[60vh] overflow-hidden">
                    {view === "day" && (
                        <DayBoard
                            anchor={anchor} techs={techs} jobs={filteredJobs.filter((j) => j.assigned_to)}
                            setDraggingId={setDraggingId} draggingId={draggingId}
                            dragOver={dragOver} setDragOver={setDragOver}
                            onDrop={dropOnSlot}
                        />
                    )}
                    {view === "week" && (
                        <WeekBoard anchor={anchor} jobs={filteredJobs} techs={techs}
                            setDraggingId={setDraggingId} draggingId={draggingId}
                            dragOver={dragOver} setDragOver={setDragOver}
                            onDrop={(techId, dayIso) => dropOnSlot(techId, dayIso)}
                        />
                    )}
                    {view === "month" && <MonthBoard anchor={anchor} jobs={filteredJobs} />}
                    {view === "map" && <DispatchMap locations={locations} jobs={filteredJobs} />}
                </main>

                {/* RIGHT: unassigned + emergency queue */}
                <UnassignedRail
                    unassigned={unassigned}
                    setDraggingId={setDraggingId}
                    draggingId={draggingId}
                    emergencyCount={emergencyCount}
                />
            </div>
            <AIDispatcherPanel />
        </div>
    );
}

/* ---------- Header ---------- */
function Header({ view, setView, anchor, setAnchor, connected, emergencyCount, filterEmergency, setFilterEmergency, onRefresh }) {
    const shift = (n) => {
        if (view === "month") { const d = new Date(anchor); d.setMonth(d.getMonth() + n); setAnchor(d); }
        else if (view === "week") setAnchor(addDays(anchor, 7 * n));
        else setAnchor(addDays(anchor, n));
    };
    const label = view === "month" ? fmtMonthYear(anchor)
        : view === "week" ? `Week of ${startOfWeek(anchor).toLocaleDateString([], { month: "short", day: "numeric" })}`
        : anchor.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });

    return (
        <div className="flex items-end justify-between flex-wrap gap-3">
            <div>
                <div className="flex items-center gap-2">
                    <div className="overline">Dispatch board</div>
                    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold tracking-wider uppercase ${connected ? "text-emerald-600" : "text-slate-400"}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`} />
                        {connected ? "Live" : "Connecting…"}
                    </span>
                </div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1" data-testid="dispatch-title">{label}</h1>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
                <button onClick={() => setFilterEmergency((v) => !v)} data-testid="dispatch-emergency-toggle"
                    className={`h-9 px-3 border text-sm font-semibold flex items-center gap-1.5
                        ${filterEmergency ? "bg-[#DC2626] text-white border-[#DC2626]" : "border-slate-300 hover:bg-red-50 text-[#DC2626]"}`}>
                    <Lightning weight={filterEmergency ? "fill" : "bold"} size={14} />
                    {emergencyCount > 0 ? `${emergencyCount} Emergency` : "Emergency"}
                </button>
                <div className="inline-flex border border-slate-300 bg-white" data-testid="dispatch-view-switch">
                    {VIEWS.map((v) => {
                        const Icon = v.icon;
                        const active = view === v.id;
                        return (
                            <button key={v.id} onClick={() => setView(v.id)}
                                data-testid={`dispatch-view-${v.id}`}
                                className={`h-9 px-3 text-sm font-medium flex items-center gap-1.5 ${active ? "bg-[#0F172A] text-white" : "hover:bg-slate-50"}`}>
                                <Icon size={14} />
                                <span className="hidden sm:inline">{v.label}</span>
                            </button>
                        );
                    })}
                </div>
                <div className="inline-flex border border-slate-300 bg-white">
                    <button onClick={() => shift(-1)} data-testid="dispatch-prev" className="h-9 w-9 hover:bg-slate-50 flex items-center justify-center"><CaretLeft /></button>
                    <button onClick={() => setAnchor(new Date(new Date().setHours(0,0,0,0)))} className="h-9 px-3 border-x border-slate-300 hover:bg-slate-50 text-sm font-medium">Today</button>
                    <button onClick={() => shift(1)} data-testid="dispatch-next" className="h-9 w-9 hover:bg-slate-50 flex items-center justify-center"><CaretRight /></button>
                </div>
            </div>
        </div>
    );
}

/* ---------- Tech rail ---------- */
function TechRail({ techs, locations, onOptimize }) {
    const byId = Object.fromEntries(locations.map((l) => [l.id, l]));
    return (
        <aside className="bg-white border border-slate-200 p-3 space-y-2 max-h-[80vh] overflow-y-auto" data-testid="dispatch-tech-rail">
            <div className="overline mb-1">Technicians · {techs.length}</div>
            {techs.length === 0 && <div className="text-xs text-slate-500 py-4 text-center">No techs yet.</div>}
            {techs.map((t) => {
                const loc = byId[t.id] || {};
                const statusKey = loc.tech_status || "off_duty";
                const badge = TECH_STATUS_BADGE[statusKey];
                return (
                    <div key={t.id} className="border border-slate-200 p-3" data-testid={`dispatch-tech-${t.id}`}>
                        <div className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                                <div className="font-semibold text-sm truncate">{t.name}</div>
                                <div className="flex items-center gap-1 mt-0.5">
                                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: badge.color }} />
                                    <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: badge.color }}>{badge.label}</span>
                                </div>
                            </div>
                            <button onClick={() => onOptimize(t.id)} data-testid={`dispatch-optimize-${t.id}`}
                                title="Optimize today's route" className="h-7 w-7 border border-slate-300 hover:bg-slate-50 flex items-center justify-center">
                                <MapTrifold size={12} />
                            </button>
                        </div>
                        {loc.last_location && (
                            <div className="mt-2 text-[10px] text-slate-500 font-mono">
                                {loc.last_location.lat.toFixed(4)}, {loc.last_location.lng.toFixed(4)} · {timeAgo(loc.last_location.ts)}
                            </div>
                        )}
                    </div>
                );
            })}
        </aside>
    );
}

/* ---------- Unassigned rail ---------- */
function UnassignedRail({ unassigned, setDraggingId, draggingId, emergencyCount }) {
    return (
        <aside className="bg-white border border-slate-200 p-3 space-y-2 max-h-[80vh] overflow-y-auto" data-testid="dispatch-unassigned-rail">
            <div className="overline mb-1">Unassigned · {unassigned.length}</div>
            {emergencyCount > 0 && (
                <div className="bg-[#DC2626] text-white text-xs font-bold uppercase tracking-wider px-2.5 py-1.5 flex items-center gap-1.5 mb-2">
                    <Lightning size={12} weight="fill" /> {emergencyCount} emergency open
                </div>
            )}
            {unassigned.length === 0 && (
                <div className="text-xs text-slate-500 py-4 text-center">All jobs assigned. 🙌</div>
            )}
            {unassigned.map((j) => (
                <JobCard key={j.id} job={j} compact
                    draggable onDragStart={() => setDraggingId(j.id)} onDragEnd={() => setDraggingId(null)}
                    dragging={draggingId === j.id}
                />
            ))}
        </aside>
    );
}

/* ---------- Job card ---------- */
function JobCard({ job, compact, draggable, onDragStart, onDragEnd, dragging, style }) {
    const typeColor = TYPE_COLOR[job.job_type] || TYPE_COLOR.Other;
    const priorityClass = PRIORITY_RING[job.priority || "normal"];
    const emerg = job.priority === "emergency";
    return (
        <div draggable={draggable}
            onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; onDragStart?.(e); }}
            onDragEnd={onDragEnd}
            data-testid={`dispatch-job-${job.id}`}
            className={`dispatch-card border border-slate-200 bg-white p-2 cursor-grab active:cursor-grabbing
                ${dragging ? "dragging" : ""} ${priorityClass} ${emerg ? "dispatch-card-emerg" : ""}`}
            style={{ borderLeft: `4px solid ${typeColor}`, ...style }}>
            <div className="flex items-start justify-between gap-2">
                <div className="font-semibold text-xs leading-snug truncate flex-1">{job.title}</div>
                {emerg && <Lightning size={12} weight="fill" className="text-[#DC2626] flex-shrink-0" />}
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500">
                {job.scheduled_at && <><Clock size={10} />{fmtTime(job.scheduled_at)}</>}
                {job.duration_min && <span>· {job.duration_min}m</span>}
            </div>
            {!compact && job.customer_name && (
                <div className="text-[10px] text-slate-600 truncate mt-0.5">{job.customer_name}</div>
            )}
            <div className="mt-1 flex items-center justify-between gap-1">
                <span className={`text-[9px] px-1.5 py-0.5 font-semibold uppercase tracking-wider ${STATUS_BG[job.status] || ""}`}>
                    {STATUS_LABEL[job.status]?.toLowerCase() || job.status.replace("_", " ")}
                </span>
                {job.price > 0 && <span className="text-[10px] font-mono font-semibold">${job.price.toFixed(0)}</span>}
            </div>
        </div>
    );
}

/* ---------- Day board ---------- */
function DayBoard({ anchor, techs, jobs, setDraggingId, draggingId, dragOver, setDragOver, onDrop }) {
    const dayKey = dateKey(anchor);
    const todays = jobs.filter((j) => j.scheduled_at?.startsWith(dayKey));
    const hours = Array.from({ length: HOUR_END - HOUR_START + 1 }, (_, i) => HOUR_START + i);

    const onSlot = (techId, hour) => {
        const dt = new Date(anchor); dt.setHours(hour, 0, 0, 0);
        onDrop(techId, dt.toISOString());
    };

    return (
        <div className="overflow-auto" style={{ maxHeight: "75vh" }} data-testid="dispatch-day">
            <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-50 z-10">
                    <tr>
                        <th className="text-left px-2 py-2 w-16 text-[10px] uppercase tracking-wider text-slate-500 font-semibold border-b border-slate-200">Time</th>
                        {techs.map((t) => (
                            <th key={t.id} className="text-left px-2 py-2 text-[11px] font-semibold text-slate-700 border-b border-slate-200 min-w-[160px]">
                                {t.name}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {hours.map((h) => (
                        <tr key={h}>
                            <td className="border-b border-slate-100 text-[10px] text-slate-400 font-mono align-top px-2 py-1">
                                {h % 12 || 12}:00 {h < 12 ? "AM" : "PM"}
                            </td>
                            {techs.map((t) => {
                                const slotKey = `${t.id}@${h}`;
                                const jobsHere = todays.filter((j) =>
                                    j.assigned_to === t.id && new Date(j.scheduled_at).getHours() === h
                                );
                                return (
                                    <td key={t.id} style={{ minHeight: ROW_PX }}
                                        onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOver(slotKey); }}
                                        onDragLeave={() => setDragOver((p) => (p === slotKey ? null : p))}
                                        onDrop={() => { onSlot(t.id, h); setDragOver(null); }}
                                        className={`dispatch-slot border-b border-l border-slate-100 align-top p-1 ${dragOver === slotKey ? "over" : ""}`}>
                                        <div className="space-y-1">
                                            {jobsHere.map((j) => (
                                                <JobCard key={j.id} job={j}
                                                    draggable onDragStart={() => setDraggingId(j.id)} onDragEnd={() => setDraggingId(null)}
                                                    dragging={draggingId === j.id} />
                                            ))}
                                        </div>
                                    </td>
                                );
                            })}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

/* ---------- Week board ---------- */
function WeekBoard({ anchor, jobs, techs, setDraggingId, draggingId, dragOver, setDragOver, onDrop }) {
    const start = startOfWeek(anchor);
    const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
    return (
        <div className="overflow-auto" data-testid="dispatch-week">
            <div className="grid" style={{ gridTemplateColumns: `120px repeat(${techs.length || 1}, minmax(180px,1fr))` }}>
                <div />
                {techs.map((t) => (
                    <div key={t.id} className="text-[11px] font-semibold p-2 border-b border-slate-200 bg-slate-50">{t.name}</div>
                ))}
                {days.map((d) => {
                    const dk = dateKey(d);
                    return (
                        <ROW key={dk} day={d} techs={techs} dk={dk} jobs={jobs}
                            setDraggingId={setDraggingId} draggingId={draggingId}
                            dragOver={dragOver} setDragOver={setDragOver} onDrop={onDrop} />
                    );
                })}
            </div>
        </div>
    );
}

function ROW({ day, techs, dk, jobs, setDraggingId, draggingId, dragOver, setDragOver, onDrop }) {
    return (
        <>
            <div className="border-b border-slate-100 p-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500 self-start">
                {day.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
            </div>
            {techs.map((t) => {
                const slotKey = `${t.id}@${dk}`;
                const cellJobs = jobs.filter((j) => j.assigned_to === t.id && j.scheduled_at?.startsWith(dk));
                return (
                    <div key={t.id}
                        onDragOver={(e) => { e.preventDefault(); setDragOver(slotKey); }}
                        onDragLeave={() => setDragOver((p) => (p === slotKey ? null : p))}
                        onDrop={() => { const dt = new Date(day); dt.setHours(9,0,0,0); onDrop(t.id, dt.toISOString()); setDragOver(null); }}
                        className={`dispatch-slot border-b border-l border-slate-100 min-h-[80px] p-1 space-y-1 ${dragOver === slotKey ? "over" : ""}`}>
                        {cellJobs.map((j) => (
                            <JobCard key={j.id} job={j}
                                draggable onDragStart={() => setDraggingId(j.id)} onDragEnd={() => setDraggingId(null)}
                                dragging={draggingId === j.id} compact />
                        ))}
                    </div>
                );
            })}
        </>
    );
}

/* ---------- Month board ---------- */
function MonthBoard({ anchor, jobs }) {
    const monthStart = startOfMonth(anchor);
    const gridStart = startOfWeek(monthStart);
    const cells = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
    return (
        <div className="grid grid-cols-7" data-testid="dispatch-month">
            {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
                <div key={d} className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 p-2 border-b border-slate-200 bg-slate-50">{d}</div>
            ))}
            {cells.map((d) => {
                const dk = dateKey(d);
                const list = jobs.filter((j) => j.scheduled_at?.startsWith(dk));
                const inMonth = d.getMonth() === monthStart.getMonth();
                const isToday = dk === dateKey(new Date());
                return (
                    <div key={dk} className={`min-h-[110px] border-b border-r border-slate-100 p-1.5 text-xs ${inMonth ? "bg-white" : "bg-slate-50/70 text-slate-400"} ${isToday ? "ring-2 ring-inset ring-[#1D4ED8]" : ""}`}>
                        <div className="font-semibold text-[11px] mb-1">{d.getDate()}</div>
                        <div className="space-y-0.5">
                            {list.slice(0, 3).map((j) => (
                                <div key={j.id} title={j.title}
                                    className="truncate text-[10px] px-1 py-0.5"
                                    style={{ background: TYPE_COLOR[j.job_type] + "20", borderLeft: `2px solid ${TYPE_COLOR[j.job_type]}` }}>
                                    {fmtTime(j.scheduled_at)} {j.title}
                                </div>
                            ))}
                            {list.length > 3 && <div className="text-[10px] text-slate-500">+{list.length - 3} more</div>}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

/* ---------- Map view ---------- */
function DispatchMap({ locations, jobs }) {
    const techMarkers = locations.filter((l) => l.last_location && l.role === "technician");
    // Compute centre from any location, else Austin TX fallback
    const centre = techMarkers[0]?.last_location
        ? [techMarkers[0].last_location.lat, techMarkers[0].last_location.lng]
        : [30.2672, -97.7431];
    const openJobs = jobs.filter((j) => j.status !== "completed" && j.status !== "cancelled" && j.location);
    return (
        <div style={{ height: "75vh" }} data-testid="dispatch-map">
            <MapContainer center={centre} zoom={11} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {techMarkers.map((t) => {
                    const badge = TECH_STATUS_BADGE[t.tech_status || "off_duty"];
                    return (
                        <CircleMarker key={t.id} center={[t.last_location.lat, t.last_location.lng]}
                            radius={10} pathOptions={{ color: badge.color, fillColor: badge.color, fillOpacity: 0.85 }}>
                            <Popup>
                                <div style={{ fontFamily: "inherit" }}>
                                    <strong>{t.name}</strong><br/>
                                    {badge.label}<br/>
                                    <small>{timeAgo(t.last_location.ts)}</small>
                                </div>
                            </Popup>
                        </CircleMarker>
                    );
                })}
                {openJobs.map((j) => j.location && (
                    <Marker key={j.id} position={[j.location.lat, j.location.lng]}>
                        <Popup><strong>{j.title}</strong><br/>{j.address}</Popup>
                    </Marker>
                ))}
            </MapContainer>
            <div className="text-[10px] text-slate-500 px-2 py-1">
                Tip: Geocoding is on the roadmap. Map currently plots techs with live GPS only.
            </div>
        </div>
    );
}

function timeAgo(iso) {
    const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return `${h}h ago`;
}

function Loader() {
    return (
        <div className="min-h-[60vh] flex items-center justify-center">
            <CircleNotch size={32} className="animate-spin text-slate-400" />
        </div>
    );
}
