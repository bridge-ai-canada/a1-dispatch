import { useEffect, useMemo, useState } from "react";
import api from "../lib/api";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";

const HOURS = Array.from({ length: 11 }, (_, i) => 7 + i); // 7am..5pm

function startOfWeek(d) {
    const date = new Date(d);
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1); // Monday start
    date.setHours(0, 0, 0, 0);
    date.setDate(diff);
    return date;
}

export default function Schedule() {
    const [jobs, setJobs] = useState([]);
    const [team, setTeam] = useState([]);
    const [anchor, setAnchor] = useState(startOfWeek(new Date()));

    useEffect(() => {
        api.get("/jobs").then((r) => setJobs(r.data));
        api.get("/team").then((r) => setTeam(r.data));
    }, []);

    const days = useMemo(() => Array.from({ length: 7 }, (_, i) => {
        const d = new Date(anchor); d.setDate(anchor.getDate() + i); return d;
    }), [anchor]);

    const techs = team.filter((t) => t.role === "technician" || t.role === "owner");

    const jobsByDay = useMemo(() => {
        const map = {};
        days.forEach((d) => { map[d.toDateString()] = []; });
        jobs.forEach((j) => {
            if (!j.scheduled_at) return;
            const k = new Date(j.scheduled_at).toDateString();
            if (map[k] !== undefined) map[k].push(j);
        });
        return map;
    }, [jobs, days]);

    const shift = (delta) => {
        const d = new Date(anchor); d.setDate(d.getDate() + delta * 7); setAnchor(d);
    };

    return (
        <div data-testid="schedule-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Dispatch</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Schedule</h1>
                    <p className="text-sm text-slate-500 mt-2">
                        Week of {anchor.toLocaleDateString([], { month: "long", day: "numeric" })}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => shift(-1)} data-testid="prev-week-button" className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><CaretLeft /></button>
                    <button onClick={() => setAnchor(startOfWeek(new Date()))} className="h-9 px-3 border border-slate-300 hover:bg-slate-50 text-sm font-medium">Today</button>
                    <button onClick={() => shift(1)} data-testid="next-week-button" className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><CaretRight /></button>
                </div>
            </div>

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
                                const dayJobs = (jobsByDay[d.toDateString()] || []).filter((j) => new Date(j.scheduled_at).getHours() === h);
                                return (
                                    <div key={`${d.toISOString()}-${h}`} className="border-r border-b border-slate-200 min-h-[60px] p-1 space-y-1">
                                        {dayJobs.map((j) => {
                                            const tech = techs.find((t) => t.id === j.assigned_to);
                                            return (
                                                <div key={j.id}
                                                    data-testid={`schedule-job-${j.id}`}
                                                    className={`text-xs p-1.5 border-l-2 ${j.status === "completed" ? "bg-emerald-50 border-emerald-500" : "bg-blue-50 border-[#1D4ED8]"}`}>
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
        </div>
    );
}
