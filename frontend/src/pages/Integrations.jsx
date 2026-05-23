import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { API_BASE, formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    Plugs, CheckCircle, Warning, ArrowsClockwise, Trash, Plus,
    Lightning, ArrowSquareOut, Lock, Pencil, FloppyDisk,
} from "@phosphor-icons/react";

const CATEGORIES = {
    accounting: { label: "Accounting", color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    payments:   { label: "Payments",   color: "bg-violet-50 text-violet-700 border-violet-200" },
    messaging:  { label: "Messaging",  color: "bg-rose-50 text-rose-700 border-rose-200" },
    calendar:   { label: "Calendar",   color: "bg-blue-50 text-blue-700 border-blue-200" },
    email:      { label: "Email",      color: "bg-orange-50 text-orange-700 border-orange-200" },
    video:      { label: "Video",      color: "bg-sky-50 text-sky-700 border-sky-200" },
    maps:       { label: "Maps",       color: "bg-teal-50 text-teal-700 border-teal-200" },
};

export default function Integrations() {
    const [list, setList] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [filter, setFilter] = useState("all");
    const [params] = useSearchParams();

    const load = async () => {
        try {
            const { data } = await api.get("/integrations");
            setList(data.integrations);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setLoading(false); }
    };
    useEffect(() => { load(); }, []);

    useEffect(() => {
        const p = params.get("provider"); const r = params.get("result");
        if (p && r === "connected") toast.success(`${p} connected`);
        if (p && r === "error") toast.error(`${p} connection failed`);
    }, [params]);

    const cats = useMemo(() => ["all", ...new Set(list.map((i) => i.category))], [list]);
    const filtered = filter === "all" ? list : list.filter((i) => i.category === filter);

    return (
        <div data-testid="integrations-page" className="space-y-6 max-w-[1600px]">
            <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 flex items-center gap-2">
                        <Plugs size={28}/> Integrations
                    </h1>
                    <p className="text-sm text-slate-500 mt-1">
                        Connect accounting, payments, calendars and more. Credentials are encrypted at rest.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Link to="/app/integrations/webhooks" data-testid="goto-webhooks"
                        className="px-4 py-2 rounded-xl border border-slate-200 bg-white text-sm font-bold inline-flex items-center gap-2 hover:bg-slate-50">
                        <Lightning size={14}/> Webhooks
                    </Link>
                    <Link to="/app/settings/api-keys" data-testid="goto-api-keys"
                        className="px-4 py-2 rounded-xl border border-slate-200 bg-white text-sm font-bold inline-flex items-center gap-2 hover:bg-slate-50">
                        <Lock size={14}/> API tokens
                    </Link>
                </div>
            </header>

            <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-3">
                {cats.map((c) => (
                    <button key={c} onClick={() => setFilter(c)} data-testid={`int-filter-${c}`}
                        className={`px-3 py-1.5 text-xs font-bold rounded-full border ${filter === c ? "bg-slate-900 text-white border-slate-900" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
                        {c === "all" ? "All" : (CATEGORIES[c]?.label || c)}
                    </button>
                ))}
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {loading && Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="bg-white border border-slate-200 rounded-2xl p-5 animate-pulse">
                        <div className="flex items-center gap-3">
                            <div className="w-11 h-11 rounded-xl bg-slate-200"/>
                            <div className="flex-1 space-y-2">
                                <div className="h-3 w-24 bg-slate-200 rounded"/>
                                <div className="h-2 w-16 bg-slate-100 rounded"/>
                            </div>
                        </div>
                        <div className="mt-4 h-3 w-full bg-slate-100 rounded"/>
                        <div className="mt-2 h-3 w-2/3 bg-slate-100 rounded"/>
                    </div>
                ))}
                {!loading && filtered.map((i) => (
                    <IntegrationCard key={i.key} integ={i} onClick={() => setSelected(i)}/>
                ))}
            </div>

            {selected && (
                <IntegrationDetail
                    integ={selected}
                    onClose={() => { setSelected(null); load(); }}
                />
            )}
        </div>
    );
}

function IntegrationCard({ integ, onClick }) {
    const cat = CATEGORIES[integ.category] || { label: integ.category, color: "" };
    return (
        <button onClick={onClick}
            data-testid={`int-card-${integ.key}`}
            className="text-left bg-white border border-slate-200 rounded-2xl p-5 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center text-white text-lg font-extrabold"
                        style={{ background: integ.color }}>
                        {integ.name.slice(0, 1)}
                    </div>
                    <div>
                        <div className="font-extrabold text-base">{integ.name}</div>
                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${cat.color}`}>{cat.label}</span>
                    </div>
                </div>
                {integ.connected ? (
                    <span className="text-xs font-bold text-emerald-700 flex items-center gap-1"><CheckCircle size={14} weight="fill"/>Connected</span>
                ) : (
                    <span className="text-xs font-bold text-slate-400">Not set</span>
                )}
            </div>
            <p className="text-sm text-slate-600 mt-3 leading-snug">{integ.description}</p>
            <div className="mt-4 flex items-center gap-3 text-[11px] text-slate-500">
                {integ.supports_webhooks && <span>· Webhooks</span>}
                {integ.supports_sync && <span>· Sync</span>}
                {integ.last_sync_at && (
                    <span className={integ.last_sync_status === "error" ? "text-rose-600" : ""}>
                        · last sync {new Date(integ.last_sync_at).toLocaleString()}
                    </span>
                )}
            </div>
        </button>
    );
}

function IntegrationDetail({ integ, onClose }) {
    const [busy, setBusy] = useState(false);
    const [form, setForm] = useState({});
    const [edit, setEdit] = useState(!integ.connected);
    const isOAuth = integ.auth_mode === "oauth2";

    const startOAuth = () => {
        window.location.href = `${API_BASE}/integrations/${integ.key}/start`;
    };

    const saveFields = async () => {
        setBusy(true);
        try {
            await api.post(`/integrations/${integ.key}`, { data: form });
            toast.success("Saved");
            setEdit(false);
            onClose();
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setBusy(false); }
    };

    const disconnect = async () => {
        if (!confirm(`Disconnect ${integ.name}? Stored credentials will be erased.`)) return;
        setBusy(true);
        try {
            await api.delete(`/integrations/${integ.key}`);
            toast.success("Disconnected");
            onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };

    const test = async () => {
        setBusy(true);
        try {
            const { data } = await api.post(`/integrations/${integ.key}/test`);
            data.ok ? toast.success(data.detail || "Connection OK") : toast.error(data.error || "Failed");
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };

    const sync = async () => {
        setBusy(true);
        try {
            const { data } = await api.post(`/integrations/${integ.key}/sync`);
            toast.success(data.ok ? `Sync ran (${data.count || 0} records)` : (data.error || "Sync failed"));
            onClose();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };

    return (
        <div className="fixed inset-0 z-40 bg-black/40 flex items-end sm:items-center sm:justify-center p-0 sm:p-6"
             data-testid="int-detail-modal" onClick={onClose}>
            <div className="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-xl max-h-[92vh] overflow-y-auto"
                 onClick={(e) => e.stopPropagation()}>
                <header className="p-5 border-b border-slate-200 flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl flex items-center justify-center text-white text-lg font-extrabold"
                        style={{ background: integ.color }}>{integ.name.slice(0,1)}</div>
                    <div className="flex-1">
                        <div className="font-extrabold text-lg">{integ.name}</div>
                        <div className="text-xs text-slate-500">{integ.description}</div>
                    </div>
                    <button onClick={onClose} className="px-2 py-1 text-slate-400 hover:text-slate-700 text-xl" aria-label="Close">×</button>
                </header>

                <div className="p-5 space-y-4">
                    {/* Status row */}
                    <div className={`p-3 rounded-xl border ${integ.connected ? "bg-emerald-50 border-emerald-200" : "bg-slate-50 border-slate-200"}`}>
                        <div className="text-xs font-bold uppercase tracking-wide flex items-center gap-2">
                            {integ.connected ? <CheckCircle weight="fill" className="text-emerald-600" size={14}/> : <Warning size={14}/>}
                            {integ.connected ? "Connected" : "Not connected"}
                        </div>
                        {integ.last_sync_at && (
                            <div className="text-xs mt-1 text-slate-600">
                                Last sync: {new Date(integ.last_sync_at).toLocaleString()}
                                {integ.last_error && <span className="text-rose-600"> · {integ.last_error}</span>}
                            </div>
                        )}
                        {!integ.platform_configured && isOAuth && (
                            <div className="text-xs mt-1 text-amber-700">
                                Platform OAuth client not configured. Add the relevant CLIENT_ID + CLIENT_SECRET to backend env.
                            </div>
                        )}
                    </div>

                    {/* OAuth flow */}
                    {isOAuth && (
                        <div className="space-y-2">
                            <button onClick={startOAuth} disabled={busy || !integ.platform_configured}
                                data-testid={`int-${integ.key}-connect-btn`}
                                className="w-full px-4 py-2.5 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm disabled:opacity-50 inline-flex items-center justify-center gap-2">
                                <ArrowSquareOut size={14}/> {integ.connected ? "Reconnect" : "Connect"} via OAuth
                            </button>
                            <p className="text-[11px] text-slate-500">
                                You'll be redirected to {integ.name} to authorize. We never see your password.
                            </p>
                        </div>
                    )}

                    {/* API key / token form */}
                    {!isOAuth && integ.fields?.length > 0 && (
                        <div className="space-y-3">
                            {integ.fields.map((f) => (
                                <Field key={f.key} field={f}
                                    value={form[f.key] ?? (integ.data?.[f.key] || "")}
                                    locked={!edit && integ.connected}
                                    onChange={(v) => setForm({ ...form, [f.key]: v })}/>
                            ))}
                            {edit ? (
                                <button onClick={saveFields} disabled={busy} data-testid={`int-${integ.key}-save-btn`}
                                    className="w-full px-4 py-2.5 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm inline-flex items-center justify-center gap-2">
                                    <FloppyDisk size={14}/> Save credentials
                                </button>
                            ) : (
                                integ.connected && (
                                    <button onClick={() => setEdit(true)}
                                        className="w-full px-4 py-2.5 rounded-xl border border-slate-300 text-sm font-bold inline-flex items-center justify-center gap-2">
                                        <Pencil size={14}/> Edit
                                    </button>
                                )
                            )}
                        </div>
                    )}

                    {/* Action row */}
                    {integ.connected && (
                        <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-100">
                            <button onClick={test} disabled={busy} data-testid={`int-${integ.key}-test-btn`}
                                className="px-3 py-2 rounded-lg border border-slate-200 text-xs font-bold hover:bg-slate-50 inline-flex items-center justify-center gap-1">
                                <Lightning size={12}/> Test
                            </button>
                            <button onClick={sync} disabled={busy || !integ.supports_sync} data-testid={`int-${integ.key}-sync-btn`}
                                className="px-3 py-2 rounded-lg border border-slate-200 text-xs font-bold hover:bg-slate-50 inline-flex items-center justify-center gap-1 disabled:opacity-30">
                                <ArrowsClockwise size={12}/> Sync
                            </button>
                            <button onClick={disconnect} disabled={busy} data-testid={`int-${integ.key}-disconnect-btn`}
                                className="px-3 py-2 rounded-lg border border-rose-200 text-rose-700 text-xs font-bold hover:bg-rose-50 inline-flex items-center justify-center gap-1">
                                <Trash size={12}/> Remove
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function Field({ field, value, locked, onChange }) {
    const isSecret = field.secret;
    const isSelect = field.type === "select";
    return (
        <label className="block">
            <div className="text-xs font-bold text-slate-700 mb-1">
                {field.label}{field.required && <span className="text-rose-600"> *</span>}
            </div>
            {isSelect ? (
                <select value={value || field.default || ""} disabled={locked} onChange={(e) => onChange(e.target.value)}
                    className="w-full h-10 px-3 rounded border border-slate-300 text-sm bg-white"
                    data-testid={`int-field-${field.key}`}>
                    {field.options?.map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
            ) : (
                <input type={isSecret && !locked ? "password" : "text"} value={value || ""} disabled={locked}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={isSecret ? "•••••••••" : ""}
                    data-testid={`int-field-${field.key}`}
                    className="w-full h-10 px-3 rounded border border-slate-300 text-sm font-mono bg-white"/>
            )}
        </label>
    );
}
