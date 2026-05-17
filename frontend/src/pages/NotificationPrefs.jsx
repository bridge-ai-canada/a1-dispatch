import { useEffect, useState } from "react";
import api from "../lib/api";
import { toast } from "sonner";
import { BellRinging, MoonStars, FloppyDisk } from "@phosphor-icons/react";

const EVENTS = [
    { key: "job_assigned", label: "New / reassigned jobs", hint: "Dispatch sends you a new work order" },
    { key: "job_rescheduled", label: "Job rescheduled", hint: "Your scheduled job moves to a new time" },
    { key: "payment_received", label: "Payment received", hint: "A customer's invoice clears in Stripe" },
    { key: "tip_received", label: "Tip received", hint: "A grateful customer adds a tip" },
    { key: "rating_created", label: "Customer ratings", hint: "A new star rating lands for one of your visits" },
    { key: "rating_low_alert", label: "Low-rating alerts (owner)", hint: "Heads-up when a job gets 1 or 2 stars" },
    { key: "recurring_materialized", label: "Recurring job created", hint: "A maintenance plan generates the next visit" },
];

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const fmtHour = (h) => `${(h % 12) || 12}:00 ${h < 12 ? "AM" : "PM"}`;

export default function NotificationPrefs() {
    const [prefs, setPrefs] = useState(null);
    const [saving, setSaving] = useState(false);
    const [quietOn, setQuietOn] = useState(false);

    useEffect(() => {
        api.get("/me/push-prefs").then((r) => {
            setPrefs(r.data);
            setQuietOn(r.data.quiet_hours_start !== null && r.data.quiet_hours_end !== null);
        });
    }, []);

    const save = async () => {
        if (!prefs) return;
        setSaving(true);
        try {
            const payload = {
                ...prefs,
                quiet_hours_start: quietOn ? (prefs.quiet_hours_start ?? 22) : null,
                quiet_hours_end:   quietOn ? (prefs.quiet_hours_end ?? 7)   : null,
            };
            await api.put("/me/push-prefs", payload);
            setPrefs(payload);
            toast.success("Notification preferences saved");
        } catch {
            toast.error("Could not save");
        } finally {
            setSaving(false);
        }
    };

    if (!prefs) return <div className="text-sm text-slate-500">Loading…</div>;

    return (
        <div data-testid="notif-prefs-page" className="space-y-6 max-w-2xl">
            <div>
                <div className="overline">Profile</div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Notification Preferences</h1>
                <p className="text-sm text-slate-500 mt-2">
                    Choose exactly which pushes you want — no more, no less. Quiet hours silence everything overnight.
                </p>
            </div>

            <div className="border border-slate-200 bg-white">
                <div className="px-5 py-3 border-b border-slate-200 flex items-center gap-2">
                    <BellRinging size={14} weight="duotone" className="text-[#1D4ED8]" />
                    <h2 className="text-sm font-semibold uppercase tracking-wider">Event types</h2>
                </div>
                <div className="p-5 space-y-4">
                    {EVENTS.map((e) => (
                        <div key={e.key} className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                                <div className="font-semibold text-sm">{e.label}</div>
                                <div className="text-xs text-slate-500 mt-0.5">{e.hint}</div>
                            </div>
                            <button onClick={() => setPrefs({ ...prefs, [e.key]: !prefs[e.key] })}
                                data-testid={`notif-toggle-${e.key}`}
                                className={`relative w-11 h-6 transition-colors flex-shrink-0 ${prefs[e.key] ? "bg-emerald-600" : "bg-slate-300"}`}>
                                <span className={`absolute top-0.5 ${prefs[e.key] ? "left-6" : "left-0.5"} w-5 h-5 bg-white transition-all`} />
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            <div className="border border-slate-200 bg-white">
                <div className="px-5 py-3 border-b border-slate-200 flex items-center gap-2">
                    <MoonStars size={14} weight="duotone" className="text-slate-500" />
                    <h2 className="text-sm font-semibold uppercase tracking-wider">Quiet hours (UTC)</h2>
                </div>
                <div className="p-5">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <div className="font-semibold text-sm">Silence all notifications</div>
                            <div className="text-xs text-slate-500 mt-0.5">Useful overnight, on the weekend, or during your kid's recital.</div>
                        </div>
                        <button onClick={() => setQuietOn((v) => !v)} data-testid="notif-quiet-toggle"
                            className={`relative w-11 h-6 transition-colors ${quietOn ? "bg-emerald-600" : "bg-slate-300"}`}>
                            <span className={`absolute top-0.5 ${quietOn ? "left-6" : "left-0.5"} w-5 h-5 bg-white transition-all`} />
                        </button>
                    </div>
                    {quietOn && (
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-medium">From</label>
                                <select value={prefs.quiet_hours_start ?? 22}
                                    onChange={(e) => setPrefs({ ...prefs, quiet_hours_start: Number(e.target.value) })}
                                    data-testid="notif-quiet-start"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 bg-white">
                                    {HOURS.map((h) => <option key={h} value={h}>{fmtHour(h)}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-medium">Until</label>
                                <select value={prefs.quiet_hours_end ?? 7}
                                    onChange={(e) => setPrefs({ ...prefs, quiet_hours_end: Number(e.target.value) })}
                                    data-testid="notif-quiet-end"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 bg-white">
                                    {HOURS.map((h) => <option key={h} value={h}>{fmtHour(h)}</option>)}
                                </select>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="flex justify-end">
                <button onClick={save} disabled={saving} data-testid="notif-save"
                    className="h-11 px-6 bg-[#1D4ED8] text-white font-semibold hover:opacity-90 disabled:opacity-50 flex items-center gap-2">
                    <FloppyDisk size={14} weight="bold" /> {saving ? "Saving…" : "Save preferences"}
                </button>
            </div>
        </div>
    );
}
