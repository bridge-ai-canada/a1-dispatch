import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { API_BASE } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import { startGoogleLogin } from "./AuthCallback";
import { Wrench, MapPin, Clock, CreditCard, GoogleLogo, SignOut } from "@phosphor-icons/react";

const STATUS_COLORS = {
    unscheduled: "bg-slate-100 text-slate-700",
    scheduled: "bg-blue-50 text-[#1D4ED8]",
    in_progress: "bg-amber-50 text-amber-700",
    completed: "bg-emerald-50 text-emerald-700",
    cancelled: "bg-red-50 text-[#DC2626]",
};

export default function Portal() {
    const { user, loading, logout } = useAuth();
    const [jobs, setJobs] = useState([]);
    const [companies, setCompanies] = useState([]);

    useEffect(() => {
        if (!user || user.role !== "customer") return;
        api.get("/portal/jobs").then((r) => setJobs(r.data)).catch(() => {});
        api.get("/portal/companies").then((r) => setCompanies(r.data)).catch(() => {});
    }, [user]);

    if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;

    if (!user) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
                <div className="bg-white border border-slate-200 p-8 max-w-sm w-full">
                    <Brand />
                    <div className="mt-8">
                        <div className="overline">Customer portal</div>
                        <h1 className="font-display text-3xl font-extrabold tracking-tighter mt-2">Track your service</h1>
                        <p className="text-sm text-slate-600 mt-2">Sign in with your Google account to see your visits and invoices.</p>
                    </div>
                    <button onClick={() => startGoogleLogin("/auth/callback")} data-testid="portal-google-login"
                        className="mt-8 w-full flex items-center justify-center gap-2 border border-slate-300 px-4 py-3 hover:bg-slate-50 font-semibold">
                        <GoogleLogo size={18} weight="bold" /> Continue with Google
                    </button>
                    <div className="mt-6 text-center text-xs text-slate-400">
                        Are you a contractor? <Link to="/login" className="text-[#1D4ED8] font-semibold">Staff sign in</Link>
                    </div>
                </div>
            </div>
        );
    }

    if (user.role !== "customer") {
        return <div className="min-h-screen flex items-center justify-center text-slate-500">Portal is for customers only.</div>;
    }

    const upcoming = jobs.filter((j) => j.scheduled_at && new Date(j.scheduled_at) >= new Date() && j.status !== "completed");
    const past = jobs.filter((j) => j.status === "completed" || (j.scheduled_at && new Date(j.scheduled_at) < new Date()));
    const requests = jobs.filter((j) => j.status === "unscheduled");

    return (
        <div className="min-h-screen bg-white" data-testid="portal-page">
            <header className="border-b border-slate-200">
                <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
                    <Brand />
                    <div className="flex items-center gap-3">
                        <div className="text-right text-sm hidden sm:block">
                            <div className="font-medium">{user.name}</div>
                            <div className="text-xs text-slate-500">{user.email}</div>
                        </div>
                        <button onClick={logout} className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"
                            data-testid="portal-logout-button"><SignOut size={16} /></button>
                    </div>
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-6 py-10 space-y-10">
                <div>
                    <div className="overline">Your service</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Hi {user.name?.split(" ")[0]}</h1>
                    <p className="text-sm text-slate-500 mt-2">
                        {jobs.length === 0 ? "No service history yet." : `${jobs.length} request${jobs.length > 1 ? "s" : ""} on file.`}
                    </p>
                </div>

                {companies.length > 0 && (
                    <Section label="Book another service">
                        <div className="grid sm:grid-cols-2 gap-3">
                            {companies.map((c) => (
                                <a key={c.id} href={`/book/${c.id}`} target="_blank" rel="noopener noreferrer"
                                    data-testid={`portal-book-${c.id}`}
                                    className="border border-slate-200 p-4 hover:border-[#1D4ED8] hover:bg-blue-50/30 transition-colors flex items-center gap-3">
                                    <Wrench size={20} weight="duotone" className="text-[#1D4ED8]" />
                                    <div>
                                        <div className="font-semibold">{c.name}</div>
                                        <div className="text-xs text-slate-500">{c.industry} · Request a visit</div>
                                    </div>
                                </a>
                            ))}
                        </div>
                    </Section>
                )}

                <Group title="Upcoming" jobs={upcoming} empty="No visits scheduled." />
                <Group title="Pending requests" jobs={requests} empty="No pending requests." />
                <Group title="Past visits" jobs={past} empty="No past visits yet." showInvoice />
            </main>
        </div>
    );
}

function Section({ label, children }) {
    return (
        <section>
            <div className="overline mb-3">{label}</div>
            {children}
        </section>
    );
}

function Group({ title, jobs, empty, showInvoice }) {
    return (
        <Section label={`${title} · ${jobs.length}`}>
            {jobs.length === 0 ? (
                <div className="text-sm text-slate-500 border border-dashed border-slate-300 p-6 text-center">{empty}</div>
            ) : (
                <div className="space-y-3">
                    {jobs.map((j) => (
                        <div key={j.id} className="border border-slate-200 p-4" data-testid={`portal-job-${j.id}`}>
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <div className="font-display text-lg font-extrabold tracking-tight">{j.title}</div>
                                    {j.scheduled_at && (
                                        <div className="text-sm text-slate-600 mt-0.5 flex items-center gap-1.5">
                                            <Clock size={14} className="text-slate-400" />
                                            {new Date(j.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
                                        </div>
                                    )}
                                    {j.address && <div className="text-sm text-slate-600 mt-0.5 flex items-center gap-1.5">
                                        <MapPin size={14} className="text-slate-400" /> {j.address}
                                    </div>}
                                </div>
                                <span className={`text-[10px] px-2 py-1 font-semibold uppercase tracking-wider ${STATUS_COLORS[j.status]}`}>
                                    {j.status.replace("_"," ")}
                                </span>
                            </div>
                            <div className="mt-3 flex items-center justify-between">
                                <div className="font-mono text-sm">${(j.price || 0).toFixed(2)} {j.paid && <span className="ml-2 text-emerald-600 font-semibold">PAID</span>}</div>
                                {showInvoice && j.price > 0 && (
                                    <a href={`${API_BASE}/jobs/${j.id}/invoice.pdf`} target="_blank" rel="noopener noreferrer"
                                        className="text-xs flex items-center gap-1 px-2 py-1 border border-slate-300 hover:bg-slate-50">
                                        <CreditCard size={12} /> View invoice
                                    </a>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </Section>
    );
}
