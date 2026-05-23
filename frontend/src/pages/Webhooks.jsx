import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    Lightning, Plus, Trash, ArrowsClockwise, CheckCircle,
    ArrowLeft, Copy, Check, Broadcast,
} from "@phosphor-icons/react";

export default function Webhooks() {
    const [subs, setSubs] = useState([]);
    const [eventTypes, setEventTypes] = useState([]);
    const [deliveries, setDeliveries] = useState([]);
    const [showCreate, setShowCreate] = useState(false);
    const [newSecret, setNewSecret] = useState(null);

    const load = async () => {
        try {
            const [s, d] = await Promise.all([
                api.get("/webhooks/subscriptions"),
                api.get("/webhooks/deliveries"),
            ]);
            setSubs(s.data.subscriptions);
            setEventTypes(s.data.event_types);
            setDeliveries(d.data.deliveries);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { load(); }, []);

    const deleteSub = async (id) => {
        if (!confirm("Delete this webhook subscription?")) return;
        try { await api.delete(`/webhooks/subscriptions/${id}`); toast.success("Deleted"); await load(); }
        catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const toggleActive = async (sub) => {
        try {
            await api.patch(`/webhooks/subscriptions/${sub.id}`, { active: !sub.active });
            await load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const testSub = async (id) => {
        try {
            const { data } = await api.post(`/webhooks/subscriptions/${id}/test`);
            data.ok ? toast.success(`Ping delivered (${data.status_code})`)
                    : toast.error(`Ping failed: ${data.error || data.status_code}`);
            await load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    return (
        <div data-testid="webhooks-page" className="space-y-6 max-w-[1400px]">
            <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <Link to="/app/integrations" className="text-xs text-[#1D4ED8] font-bold inline-flex items-center gap-1 mb-2">
                        <ArrowLeft size={12}/> Back to integrations
                    </Link>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
                        <Lightning size={28}/> Webhooks
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Subscribe to events from A1 Field Pro and receive HMAC-signed POSTs to your URLs.
                    </p>
                </div>
                <button onClick={() => setShowCreate(true)} data-testid="webhook-create-btn"
                    className="px-4 py-2.5 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm inline-flex items-center gap-2">
                    <Plus size={14}/> New subscription
                </button>
            </header>

            {newSecret && (
                <NewSecretBanner secret={newSecret} onDismiss={() => setNewSecret(null)}/>
            )}

            <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-200 font-bold text-sm flex items-center justify-between">
                    <span>Active subscriptions</span>
                    <span className="text-xs text-slate-500">{subs.length}</span>
                </div>
                {subs.length === 0 ? (
                    <div className="p-10 text-center text-slate-500 text-sm">
                        <Broadcast size={36} className="mx-auto text-slate-300 mb-2"/>
                        No subscriptions yet. Create one to receive realtime events.
                    </div>
                ) : (
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                            <tr>
                                <th className="text-left p-3">URL</th>
                                <th className="text-left p-3">Events</th>
                                <th className="text-left p-3">Secret</th>
                                <th className="text-left p-3">Status</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {subs.map((s) => (
                                <tr key={s.id} className="border-t border-slate-100" data-testid={`webhook-row-${s.id}`}>
                                    <td className="p-3 font-mono text-xs truncate max-w-[260px]">{s.url}</td>
                                    <td className="p-3">
                                        <div className="flex flex-wrap gap-1">
                                            {(s.events || []).slice(0, 3).map((e) => (
                                                <span key={e} className="text-[10px] bg-slate-100 px-2 py-0.5 rounded font-bold">{e}</span>
                                            ))}
                                            {s.events?.length > 3 && <span className="text-[10px] text-slate-500">+{s.events.length - 3}</span>}
                                        </div>
                                    </td>
                                    <td className="p-3 font-mono text-xs text-slate-500">{s.secret_visible}</td>
                                    <td className="p-3">
                                        <button onClick={() => toggleActive(s)}
                                            data-testid={`webhook-toggle-${s.id}`}
                                            className={`text-xs font-bold px-2 py-1 rounded border ${s.active ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-slate-50 border-slate-200 text-slate-500"}`}>
                                            {s.active ? "Active" : "Paused"}
                                        </button>
                                    </td>
                                    <td className="p-3 text-right">
                                        <button onClick={() => testSub(s.id)} data-testid={`webhook-test-${s.id}`}
                                            className="p-2 rounded hover:bg-slate-50" title="Send test ping">
                                            <Lightning size={14}/>
                                        </button>
                                        <button onClick={() => deleteSub(s.id)} data-testid={`webhook-delete-${s.id}`}
                                            className="p-2 rounded hover:bg-rose-50 text-rose-700" title="Delete">
                                            <Trash size={14}/>
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </section>

            <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-200 font-bold text-sm flex items-center justify-between">
                    <span>Recent deliveries</span>
                    <button onClick={load} className="text-xs text-[#1D4ED8] inline-flex items-center gap-1">
                        <ArrowsClockwise size={12}/> Refresh
                    </button>
                </div>
                {deliveries.length === 0 ? (
                    <div className="p-8 text-center text-slate-500 text-sm">No deliveries yet.</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                            <tr>
                                <th className="text-left p-3">Event</th>
                                <th className="text-left p-3">URL</th>
                                <th className="text-left p-3">Time</th>
                                <th className="text-left p-3">Attempt</th>
                                <th className="text-left p-3">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {deliveries.slice(0, 50).map((d) => (
                                <tr key={d.id} className="border-t border-slate-100" data-testid={`delivery-row-${d.id}`}>
                                    <td className="p-3 font-mono text-xs">{d.event}</td>
                                    <td className="p-3 font-mono text-xs truncate max-w-[260px]">{d.url}</td>
                                    <td className="p-3 text-xs">{new Date(d.created_at).toLocaleString()}</td>
                                    <td className="p-3 text-xs">#{d.attempt}</td>
                                    <td className="p-3">
                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                                            d.status === "delivered" ? "bg-emerald-100 text-emerald-700" :
                                            d.status === "pending" ? "bg-amber-100 text-amber-700" :
                                            "bg-rose-100 text-rose-700"
                                        }`}>
                                            {d.status} {d.status_code ? `(${d.status_code})` : ""}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </section>

            {showCreate && (
                <CreateSubscriptionModal
                    eventTypes={eventTypes}
                    onClose={() => setShowCreate(false)}
                    onCreated={(secret) => { setShowCreate(false); setNewSecret(secret); load(); }}
                />
            )}
        </div>
    );
}

function CreateSubscriptionModal({ eventTypes, onClose, onCreated }) {
    const [url, setUrl] = useState("");
    const [events, setEvents] = useState([]);
    const [description, setDescription] = useState("");
    const [busy, setBusy] = useState(false);

    const toggle = (e) => setEvents(events.includes(e) ? events.filter((x) => x !== e) : [...events, e]);

    const submit = async () => {
        if (!url || events.length === 0) { toast.error("URL and at least one event"); return; }
        setBusy(true);
        try {
            const { data } = await api.post("/webhooks/subscriptions", { url, events, description, active: true });
            toast.success("Subscription created");
            onCreated(data.secret_shown_once);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };

    return (
        <div className="fixed inset-0 z-40 bg-black/40 flex items-end sm:items-center sm:justify-center p-0 sm:p-6" onClick={onClose}>
            <div className="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-lg max-h-[92vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                <header className="p-5 border-b border-slate-200 flex items-center justify-between">
                    <div className="font-extrabold text-lg">New webhook subscription</div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl" aria-label="Close">×</button>
                </header>
                <div className="p-5 space-y-4">
                    <label className="block">
                        <div className="text-xs font-bold mb-1">Destination URL *</div>
                        <input type="url" value={url} onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://yourapi.example/webhook"
                            data-testid="webhook-url-input"
                            className="w-full h-10 px-3 rounded border border-slate-300 text-sm font-mono"/>
                    </label>
                    <label className="block">
                        <div className="text-xs font-bold mb-1">Description</div>
                        <input type="text" value={description} onChange={(e) => setDescription(e.target.value)}
                            data-testid="webhook-desc-input"
                            className="w-full h-10 px-3 rounded border border-slate-300 text-sm"/>
                    </label>
                    <div>
                        <div className="text-xs font-bold mb-2">Events *</div>
                        <div className="grid grid-cols-2 gap-1.5 max-h-[300px] overflow-y-auto pr-1">
                            {eventTypes.map((e) => (
                                <label key={e} className="flex items-center gap-2 text-xs p-1.5 rounded hover:bg-slate-50 cursor-pointer">
                                    <input type="checkbox" checked={events.includes(e)} onChange={() => toggle(e)}
                                        data-testid={`webhook-event-${e}`}/>
                                    <code className="text-[11px]">{e}</code>
                                </label>
                            ))}
                        </div>
                    </div>
                    <button onClick={submit} disabled={busy || !url || events.length === 0}
                        data-testid="webhook-submit-btn"
                        className="w-full px-4 py-2.5 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm disabled:opacity-50">
                        Create subscription
                    </button>
                </div>
            </div>
        </div>
    );
}

function NewSecretBanner({ secret, onDismiss }) {
    const [copied, setCopied] = useState(false);
    const copy = () => { navigator.clipboard.writeText(secret); setCopied(true); toast.success("Secret copied"); setTimeout(() => setCopied(false), 1500); };
    return (
        <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-4 space-y-2" data-testid="webhook-new-secret">
            <div className="font-extrabold text-amber-900 flex items-center gap-2">
                <CheckCircle weight="fill"/> Save your signing secret — it's only shown once
            </div>
            <div className="flex items-center gap-2">
                <code className="flex-1 truncate bg-white px-3 py-2 rounded border text-xs font-mono">{secret}</code>
                <button onClick={copy} className="p-2 rounded bg-amber-200 hover:bg-amber-300">
                    {copied ? <Check size={14}/> : <Copy size={14}/>}
                </button>
            </div>
            <div className="text-[11px] text-amber-700">
                Verify deliveries by computing <code>HMAC-SHA256(timestamp + "." + body)</code> with this secret
                and comparing against the <code>X-A1FP-Signature</code> header.
            </div>
            <button onClick={onDismiss} className="text-xs text-amber-700 underline">Dismiss</button>
        </div>
    );
}
