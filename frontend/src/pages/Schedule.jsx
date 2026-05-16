import { Fragment, useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

const HOURS = Array.from({ length: 11 }, (_, i) => 7 + i);

function startOfWeek(d) {
    const date = new Date(d);
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
    date.setHours(0, 0, 0, 0);
    date.setDate(diff);
    return date;
}

export default function Schedule() {
    const [jobs, setJobs] = useState([]);
    const [team, setTeam] = useState([]);
    const [anchor, setAnchor] = useState(startOfWeek(new Date()));
    const [dragOver, setDragOver] = useState(null);

    const load = () => {
        api.get("/jobs").then((r) => setJobs(r.data));
        api.get("/team").then((r) => setTeam(r.data));
    };
    useEffect(() => { load(); }, []);

    const days = useMemo(() => Array.from({ length: 7 }, (_, i) => {
        const d = new Date(anchor); d.setDate(anchor.getDate() + i); return d;
    }), [anchor]);

    const techs = team.filter((t) => t.role === "technician" || t.role === "owner");
    const unscheduled = jobs.filter((j) => !j.scheduled_at);

    const jobsByCell = useMemo(() => {
        const map = {};
        jobs.forEach((j) => {
            if (!j.scheduled_at) return;
            const dt = new Date(j.scheduled_at);
            const k = `${dt.toDateString()}|${dt.getHours()}`;
            if (!map[k]) map[k] = [];
            map[k].push(j);
        });
        return map;
    }, [jobs]);

    const shift = (delta) => {
        const d = new Date(anchor); d.setDate(d.getDate() + delta * 7); setAnchor(d);
    };

    const onDragStart = (jobId) => (e) => {
        e.dataTransfer.setData("text/plain", jobId);
        e.dataTransfer.effectAllowed = "move";
    };

    const onDrop = (day, hour) => async (e) => {
        e.preventDefault();
        const jobId = e.dataTransfer.getData("text/plain");
        setDragOver(null);
        if (!jobId) return;
        const target = new Date(day);
        target.setHours(hour, 0, 0, 0);
        try {
            await api.patch(`/jobs/${jobId}`, { scheduled_at: target.toISOString(), status: "scheduled" });
            toast.success("Rescheduled");
            load();
        } catch {
            toast.error("Could not reschedule");
        }
    };

    const allowDrop = (key) => (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOver(key); };

    return (
        <div data-testid="schedule-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Dispatch</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Schedule</h1>
                    <p className="text-sm text-slate-500 mt-2">Drag jobs onto a time slot to reschedule.</p>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => shift(-1)} data-testid="prev-week-button" className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><CaretLeft /></button>
                    <button onClick={() => setAnchor(startOfWeek(new Date()))} className="h-9 px-3 border border-slate-300 hover:bg-slate-50 text-sm font-medium">Today</button>
                    <button onClick={() => shift(1)} data-testid="next-week-button" className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><CaretRight /></button>
                </div>
            </div>

            <div className="grid lg:grid-cols-[1fr_240px] gap-4">
                <div className="border border-slate-200 overflow-x-auto">
                    <div className="grid grid-cols-8 min-w-[900px]">
                        <div className="bg-slate-50 border-r border-b border-slate-200 p-2 text-xs font-semibold overline">Hour</div>
                        {days.map((d) => (
                            <div key={d.toISOString()} className="bg-slate-50 border-r border-b border-slate-200 p-2 text-center">
                                <div className="overline">{d.toLocaleDateString([], { weekday: "short" })}</div>
                                <div className="font-display text-lg font-extrabold tracking-tighter">{d.getDate()}</div>
                            </div>
                        ))}
                        {HOURS.map((h) => (
                            <Fragment key={`h-${h}`}>
                                <div className="border-r border-b border-slate-200 p-2 text-xs text-slate-500 font-mono">
                                    {h.toString().padStart(2,"0")}:00
                                </div>
                                {days.map((d) => {
                                    const k = `${d.toDateString()}|${h}`;
                                    const dayJobs = jobsByCell[k] || [];
                                    return (
                                        <div key={k}
                                            data-testid={`cell-${k}`}
                                            onDragOver={allowDrop(k)}
                                            onDragLeave={() => setDragOver(null)}
                                            onDrop={onDrop(d, h)}
                                            className={`border-r border-b border-slate-200 min-h-[60px] p-1 space-y-1 transition-colors ${dragOver === k ? "bg-blue-50" : ""}`}>
                                            {dayJobs.map((j) => {
                                                const tech = techs.find((t) => t.id === j.assigned_to);
                                                return (
                                                    <div key={j.id}
                                                        draggable
                                                        onDragStart={onDragStart(j.id)}
                                                        data-testid={`schedule-job-${j.id}`}
                                                        className={`text-xs p-1.5 border-l-2 cursor-grab active:cursor-grabbing ${j.status === "completed" ? "bg-emerald-50 border-emerald-500" : "bg-blue-50 border-[#1D4ED8]"}`}>
                                                        <div className="font-semibold truncate">{j.title}</div>
                                                        <div className="text-slate-500 truncate">{tech?.name || "Unassigned"}</div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    );
                                })}
                            </Fragment>
                        ))}
                    </div>
                </div>

                <aside className="border border-slate-200 self-start">
                    <div className="px-4 py-3 border-b border-slate-200">
                        <div className="overline">Unscheduled · {unscheduled.length}</div>
                    </div>
                    <div className="p-3 space-y-2 max-h-[600px] overflow-y-auto">
                        {unscheduled.length === 0 && (
                            <div className="text-center text-sm text-slate-500 py-6">All scheduled.</div>
                        )}
                        {unscheduled.map((j) => (
                            <div key={j.id}
                                draggable
                                onDragStart={onDragStart(j.id)}
                                data-testid={`unscheduled-${j.id}`}
                                className="border border-slate-300 p-2 text-xs cursor-grab active:cursor-grabbing hover:bg-slate-50">
                                <div className="font-semibold truncate">{j.title}</div>
                                <div className="text-slate-500 truncate mt-0.5">{j.customer_name}</div>
                                <div className="text-slate-400 mt-0.5">{j.job_type} · ${(j.price || 0).toFixed(0)}</div>
                            </div>
                        ))}
                    </div>
                </aside>
            </div>
        </div>
    );
}
