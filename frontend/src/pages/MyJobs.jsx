import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { MapPin, Phone, Clock, CheckCircle, PlayCircle, CreditCard } from "@phosphor-icons/react";
import InstallPrompt from "../components/InstallPrompt";

const STATUS_NEXT = {
    scheduled: { label: "Start Job", next: "in_progress", color: "bg-[#1D4ED8]", icon: PlayCircle },
    in_progress: { label: "Mark Complete", next: "completed", color: "bg-emerald-600", icon: CheckCircle },
};
const STATUS_LABEL = {
    unscheduled: "Unscheduled",
    scheduled: "Scheduled",
    in_progress: "In progress",
    completed: "Completed",
    cancelled: "Cancelled",
};

export default function MyJobs() {
    const [jobs, setJobs] = useState([]);
    const load = () => api.get("/jobs", { params: { mine: true } }).then((r) => setJobs(r.data));
    useEffect(() => { load(); }, []);

    const setStatus = async (job, status) => {
        try {
            await api.patch(`/jobs/${job.id}`, { status });
            toast.success(`Marked ${status.replace("_"," ")}`);
            load();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    const charge = async (job) => {
        try {
            const { data } = await api.post("/payments/checkout", { job_id: job.id, origin_url: window.location.origin });
            window.location.href = data.url;
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    const today = new Date().toDateString();
    const todays = jobs.filter((j) => j.scheduled_at && new Date(j.scheduled_at).toDateString() === today);
    const upcoming = jobs.filter((j) => j.scheduled_at && new Date(j.scheduled_at) > new Date() && new Date(j.scheduled_at).toDateString() !== today);
    const completed = jobs.filter((j) => j.status === "completed");

    return (
        <div data-testid="my-jobs-page" className="space-y-8 max-w-2xl mx-auto">
            <div>
                <div className="overline">Field</div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">My Jobs</h1>
                <p className="text-sm text-slate-500 mt-2">{todays.length} job{todays.length === 1 ? "" : "s"} today</p>
            </div>

            <InstallPrompt variant="card" />

            <Section title="Today" jobs={todays} setStatus={setStatus} charge={charge} highlight />
            <Section title="Upcoming" jobs={upcoming} setStatus={setStatus} charge={charge} />
            <Section title="Completed" jobs={completed} setStatus={setStatus} charge={charge} muted />

            {jobs.length === 0 && (
                <div className="border border-dashed border-slate-300 p-12 text-center text-slate-500">
                    No jobs assigned yet.
                </div>
            )}
        </div>
    );
}

function Section({ title, jobs, setStatus, charge, highlight, muted }) {
    if (jobs.length === 0) return null;
    return (
        <div>
            <div className="overline mb-3">{title} · {jobs.length}</div>
            <div className="space-y-3">
                {jobs.map((j) => (
                    <JobCard key={j.id} job={j} setStatus={setStatus} charge={charge} highlight={highlight} muted={muted} />
                ))}
            </div>
        </div>
    );
}

function JobCard({ job, setStatus, charge, highlight, muted }) {
    const action = STATUS_NEXT[job.status];
    return (
        <div data-testid={`my-job-card-${job.id}`}
            className={`border ${highlight ? "border-[#DC2626]" : muted ? "border-slate-200 opacity-70" : "border-slate-300"} bg-white`}>
            <div className="p-4 border-b border-slate-200">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                        <div className="font-display text-lg font-extrabold tracking-tight">{job.title}</div>
                        <div className="text-sm text-slate-600 mt-0.5">{job.customer_name}</div>
                    </div>
                    <span className={`text-[10px] px-2 py-1 font-semibold tracking-wider uppercase ${
                        job.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                        job.status === "in_progress" ? "bg-amber-100 text-amber-700" :
                        "bg-blue-100 text-[#1D4ED8]"
                    }`}>{STATUS_LABEL[job.status]}</span>
                </div>
                <div className="mt-3 grid gap-2 text-sm text-slate-700">
                    {job.scheduled_at && (
                        <div className="flex items-center gap-2"><Clock size={16} className="text-slate-500" />
                            {new Date(job.scheduled_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })} · {job.duration_min} min
                        </div>
                    )}
                    {job.address && <div className="flex items-center gap-2"><MapPin size={16} className="text-slate-500" /> {job.address}</div>}
                    {job.customer_phone && <a href={`tel:${job.customer_phone}`} className="flex items-center gap-2 text-[#1D4ED8] font-medium"><Phone size={16} /> {job.customer_phone}</a>}
                </div>
                {job.description && <p className="mt-3 text-sm text-slate-600 leading-relaxed">{job.description}</p>}
            </div>
            <div className="p-3 flex items-center justify-between gap-2 bg-slate-50">
                <div className="font-mono font-semibold">${(job.price || 0).toFixed(0)}</div>
                <div className="flex items-center gap-2">
                    {!job.paid && job.price > 0 && (
                        <button onClick={() => charge(job)} data-testid={`mobile-charge-${job.id}`}
                            className="flex items-center gap-1 text-sm font-semibold px-4 h-12 border border-emerald-500 text-emerald-700 hover:bg-emerald-50">
                            <CreditCard size={16} /> Charge
                        </button>
                    )}
                    {action && (
                        <button onClick={() => setStatus(job, action.next)} data-testid={`mobile-status-${job.id}`}
                            className={`${action.color} text-white text-sm font-semibold px-4 h-12 flex items-center gap-1`}>
                            <action.icon size={16} weight="fill" /> {action.label}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
