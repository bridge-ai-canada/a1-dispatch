import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { API_BASE, formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    ArrowLeft, Phone, Envelope, MapPin, Sparkle, Plus, X, Trash,
    House, Wrench, ClockCounterClockwise, Paperclip, ChatCircle,
    UploadSimple, FloppyDisk,
} from "@phosphor-icons/react";

const STATUS = ["lead", "prospect", "active", "churned"];
const STATUS_COLORS = {
    lead: "bg-amber-100 text-amber-700",
    prospect: "bg-blue-100 text-[#1D4ED8]",
    active: "bg-emerald-100 text-emerald-700",
    churned: "bg-slate-200 text-slate-600",
};
const TABS = ["overview", "properties", "equipment", "history", "files"];

export default function CustomerDetail() {
    const { id } = useParams();
    const [cust, setCust] = useState(null);
    const [tab, setTab] = useState("overview");
    const [timeline, setTimeline] = useState([]);
    const [props, setProps] = useState([]);
    const [equip, setEquip] = useState([]);
    const [comms, setComms] = useState([]);
    const [files, setFiles] = useState([]);
    const [summary, setSummary] = useState(null);
    const [summarizing, setSummarizing] = useState(false);
    const [notes, setNotes] = useState("");
    const [savingNotes, setSavingNotes] = useState(false);

    const load = () => {
        api.get(`/customers/${id}`).then((r) => { setCust(r.data); setNotes(r.data.notes || ""); });
        api.get(`/customers/${id}/timeline`).then((r) => setTimeline(r.data));
        api.get(`/customers/${id}/properties`).then((r) => setProps(r.data));
        api.get(`/customers/${id}/equipment`).then((r) => setEquip(r.data));
        api.get(`/customers/${id}/communications`).then((r) => setComms(r.data));
        api.get(`/customers/${id}/files`).then((r) => setFiles(r.data));
    };
    useEffect(() => { load(); }, [id]); // eslint-disable-line

    const saveNotes = async () => {
        setSavingNotes(true);
        try {
            await api.patch(`/customers/${id}`, { notes });
            toast.success("Notes saved");
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
        finally { setSavingNotes(false); }
    };

    const setStatus = async (s) => {
        try {
            const { data } = await api.patch(`/customers/${id}`, { status: s });
            setCust(data); toast.success("Status updated");
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
    };

    const summarize = async () => {
        setSummarizing(true);
        try {
            const { data } = await api.get(`/customers/${id}/summary`);
            setSummary(data.summary);
        } catch { toast.error("Couldn't summarize"); }
        finally { setSummarizing(false); }
    };

    if (!cust) return <div className="p-8 text-slate-500">Loading...</div>;

    return (
        <div data-testid="customer-detail-page" className="space-y-6 max-w-6xl">
            <Link to="/app/customers" className="text-sm text-slate-500 hover:text-slate-900 flex items-center gap-1">
                <ArrowLeft size={14} /> All customers
            </Link>

            <div className="grid lg:grid-cols-[1fr_320px] gap-6 items-start">
                <div className="space-y-6">
                    <header className="border border-slate-200 p-6">
                        <div className="flex items-start justify-between gap-4 flex-wrap">
                            <div>
                                <div className="overline">{cust.source || "Customer"}</div>
                                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1" data-testid="customer-detail-name">{cust.name}</h1>
                                <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-700">
                                    {cust.phone && <a href={`tel:${cust.phone}`} className="flex items-center gap-1.5 hover:text-[#1D4ED8]"><Phone size={14} /> {cust.phone}</a>}
                                    {cust.email && <a href={`mailto:${cust.email}`} className="flex items-center gap-1.5 hover:text-[#1D4ED8]"><Envelope size={14} /> {cust.email}</a>}
                                    {cust.address && <div className="flex items-center gap-1.5"><MapPin size={14} /> {cust.address}</div>}
                                </div>
                            </div>
                            <select value={cust.status || "active"} onChange={(e) => setStatus(e.target.value)}
                                data-testid="customer-status-select"
                                className={`text-xs px-3 py-1.5 font-semibold uppercase tracking-wider border-0 ${STATUS_COLORS[cust.status || "active"]}`}>
                                {STATUS.map((s) => <option key={s} value={s}>{s}</option>)}
                            </select>
                        </div>
                        {(cust.tags || []).length > 0 && (
                            <div className="mt-4 flex flex-wrap gap-1.5">
                                {cust.tags.map((t) => (
                                    <span key={t} className="text-xs px-2 py-0.5 bg-slate-100 text-slate-700">{t}</span>
                                ))}
                            </div>
                        )}
                    </header>

                    <div className="border-b border-slate-200 flex gap-1 overflow-x-auto">
                        {TABS.map((t) => (
                            <button key={t} onClick={() => setTab(t)} data-testid={`tab-${t}`}
                                className={`px-4 py-2 text-sm font-medium border-b-2 capitalize whitespace-nowrap ${
                                    tab === t ? "border-[#DC2626] text-slate-900" : "border-transparent text-slate-500 hover:text-slate-900"
                                }`}>
                                {t}
                                <span className="ml-2 text-xs text-slate-400">
                                    {t === "overview" ? "" : t === "properties" ? props.length : t === "equipment" ? equip.length : t === "history" ? timeline.length : files.length}
                                </span>
                            </button>
                        ))}
                    </div>

                    {tab === "overview" && (
                        <div className="space-y-6">
                            <section className="border border-slate-200">
                                <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                                    <div className="overline">Quick notes</div>
                                    <button onClick={saveNotes} disabled={savingNotes} data-testid="save-notes-button"
                                        className="text-xs flex items-center gap-1 px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-60">
                                        <FloppyDisk size={12} /> {savingNotes ? "Saving..." : "Save"}
                                    </button>
                                </div>
                                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={4}
                                    data-testid="quick-notes-textarea"
                                    placeholder="Add anything dispatch should know about this customer..."
                                    className="w-full p-4 outline-none resize-y border-0 focus:ring-2 focus:ring-inset focus:ring-[#1D4ED8]" />
                            </section>

                            <CommunicationsBlock customerId={id} comms={comms} reload={load} />
                        </div>
                    )}

                    {tab === "properties" && <PropertiesTab customerId={id} items={props} reload={load} />}
                    {tab === "equipment" && <EquipmentTab customerId={id} items={equip} props={props} reload={load} />}
                    {tab === "history" && <TimelineTab events={timeline} />}
                    {tab === "files" && <FilesTab customerId={id} files={files} reload={load} />}
                </div>

                <aside className="border border-slate-200 p-5 space-y-4 sticky top-20" data-testid="ai-summary-card">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Sparkle size={16} weight="fill" className="text-[#DC2626]" />
                            <div className="overline">AI briefing</div>
                        </div>
                        <button onClick={summarize} disabled={summarizing} data-testid="ai-summarize-button"
                            className="text-xs px-2 py-1 border border-slate-300 hover:bg-slate-50 disabled:opacity-60">
                            {summarizing ? "Thinking..." : summary ? "Refresh" : "Generate"}
                        </button>
                    </div>
                    {summary ? (
                        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{summary}</p>
                    ) : (
                        <p className="text-sm text-slate-400 leading-relaxed">
                            Tap Generate to get a 4-line briefing — who they are, recent service pattern, equipment risks, next-best action.
                        </p>
                    )}

                    <div className="border-t border-slate-200 pt-3 space-y-2 text-sm">
                        <Stat label="Properties" value={props.length} />
                        <Stat label="Equipment" value={equip.length} />
                        <Stat label="Touchpoints" value={comms.length} />
                        <Stat label="Files" value={files.length} />
                    </div>
                </aside>
            </div>
        </div>
    );
}

function Stat({ label, value }) {
    return (
        <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">{label}</span>
            <span className="font-mono font-semibold">{value}</span>
        </div>
    );
}

function CommunicationsBlock({ customerId, comms, reload }) {
    const [open, setOpen] = useState(false);
    const ICON = { call: Phone, email: Envelope, sms: ChatCircle, note: ChatCircle, system: Wrench };
    return (
        <section className="border border-slate-200">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                <div className="overline">Communications · {comms.length}</div>
                <button onClick={() => setOpen(true)} data-testid="add-communication-button"
                    className="text-xs flex items-center gap-1 px-3 py-1.5 bg-[#1D4ED8] text-white hover:bg-[#1E40AF]">
                    <Plus size={12} /> Log touch
                </button>
            </div>
            <div className="divide-y divide-slate-200">
                {comms.length === 0 && <div className="p-6 text-sm text-slate-500 text-center">No communication logged yet.</div>}
                {comms.slice(0, 8).map((c) => {
                    const Icon = ICON[c.channel] || ChatCircle;
                    return (
                        <div key={c.id} className="p-4 flex items-start gap-3">
                            <Icon size={18} className="text-slate-400 mt-0.5 shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium">{c.summary}</div>
                                {c.body && <div className="text-xs text-slate-500 mt-1">{c.body}</div>}
                                <div className="text-[11px] text-slate-400 mt-1">
                                    {new Date(c.created_at).toLocaleString()} · {c.actor_name || "system"} · {c.channel}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
            {open && <CommModal customerId={customerId} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
        </section>
    );
}

function CommModal({ customerId, onClose, onSaved }) {
    const [form, setForm] = useState({ channel: "call", direction: "out", summary: "", body: "" });
    const [saving, setSaving] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post(`/customers/${customerId}/communications`, form);
            toast.success("Logged");
            onSaved();
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
        finally { setSaving(false); }
    };
    return (
        <Modal title="Log communication" onClose={onClose}>
            <form onSubmit={submit} className="p-6 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                    <select value={form.channel} onChange={(e) => setForm({...form, channel: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                        {["call","email","sms","note"].map((c) => <option key={c}>{c}</option>)}
                    </select>
                    <select value={form.direction} onChange={(e) => setForm({...form, direction: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                        {["out","in","internal"].map((c) => <option key={c}>{c}</option>)}
                    </select>
                </div>
                <input required placeholder="Summary" value={form.summary} onChange={(e) => setForm({...form, summary: e.target.value})}
                    data-testid="comm-summary-input"
                    className="w-full border border-slate-300 px-3 py-2.5" />
                <textarea placeholder="Details (optional)" value={form.body} onChange={(e) => setForm({...form, body: e.target.value})}
                    rows={3} className="w-full border border-slate-300 px-3 py-2" />
                <button type="submit" disabled={saving} data-testid="comm-submit-button"
                    className="w-full bg-[#1D4ED8] text-white py-2.5 font-semibold hover:bg-[#1E40AF] disabled:opacity-60">
                    {saving ? "Logging..." : "Log"}
                </button>
            </form>
        </Modal>
    );
}

function PropertiesTab({ customerId, items, reload }) {
    const [open, setOpen] = useState(false);
    const remove = async (pid) => {
        if (!window.confirm("Delete property and its equipment?")) return;
        await api.delete(`/properties/${pid}`); toast.success("Removed"); reload();
    };
    return (
        <section className="border border-slate-200">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                <div className="overline">Properties · {items.length}</div>
                <button onClick={() => setOpen(true)} data-testid="add-property-button"
                    className="text-xs flex items-center gap-1 px-3 py-1.5 bg-[#1D4ED8] text-white hover:bg-[#1E40AF]">
                    <Plus size={12} /> Add property
                </button>
            </div>
            <div className="divide-y divide-slate-200">
                {items.length === 0 && <div className="p-6 text-sm text-slate-500 text-center">No properties yet.</div>}
                {items.map((p) => (
                    <div key={p.id} className="p-4 flex items-center gap-3" data-testid={`property-row-${p.id}`}>
                        <House size={18} className="text-slate-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                            <div className="font-medium">{p.nickname || p.address}</div>
                            <div className="text-xs text-slate-500 truncate">{p.address}{p.sq_ft ? ` · ${p.sq_ft} sq ft` : ""}{p.year_built ? ` · ${p.year_built}` : ""}</div>
                        </div>
                        <button onClick={() => remove(p.id)} className="text-xs text-[#DC2626] hover:underline inline-flex items-center gap-1"><Trash size={12} /> Remove</button>
                    </div>
                ))}
            </div>
            {open && <PropertyModal customerId={customerId} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
        </section>
    );
}

function PropertyModal({ customerId, onClose, onSaved }) {
    const [form, setForm] = useState({ address: "", nickname: "", property_type: "residential", sq_ft: 0, year_built: 0 });
    const [saving, setSaving] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post(`/customers/${customerId}/properties`, {
                ...form, sq_ft: parseInt(form.sq_ft) || 0, year_built: parseInt(form.year_built) || 0,
            });
            toast.success("Property added"); onSaved();
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
        finally { setSaving(false); }
    };
    return (
        <Modal title="Add property" onClose={onClose}>
            <form onSubmit={submit} className="p-6 space-y-3">
                <input required placeholder="Address" value={form.address} onChange={(e) => setForm({...form, address: e.target.value})}
                    data-testid="property-address-input" className="w-full border border-slate-300 px-3 py-2.5" />
                <input placeholder="Nickname (e.g. 'Lake house')" value={form.nickname} onChange={(e) => setForm({...form, nickname: e.target.value})}
                    className="w-full border border-slate-300 px-3 py-2.5" />
                <div className="grid grid-cols-3 gap-3">
                    <select value={form.property_type} onChange={(e) => setForm({...form, property_type: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                        {["residential","commercial","multi-family"].map((t) => <option key={t}>{t}</option>)}
                    </select>
                    <input type="number" placeholder="Sq ft" value={form.sq_ft} onChange={(e) => setForm({...form, sq_ft: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <input type="number" placeholder="Year built" value={form.year_built} onChange={(e) => setForm({...form, year_built: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                </div>
                <button type="submit" disabled={saving} data-testid="property-submit-button"
                    className="w-full bg-[#1D4ED8] text-white py-2.5 font-semibold hover:bg-[#1E40AF] disabled:opacity-60">
                    {saving ? "Saving..." : "Add"}
                </button>
            </form>
        </Modal>
    );
}

function EquipmentTab({ customerId, items, props, reload }) {
    const [open, setOpen] = useState(false);
    const remove = async (eid) => {
        if (!window.confirm("Remove equipment?")) return;
        await api.delete(`/equipment/${eid}`); toast.success("Removed"); reload();
    };
    return (
        <section className="border border-slate-200">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                <div className="overline">Equipment · {items.length}</div>
                <button onClick={() => setOpen(true)} disabled={props.length === 0} data-testid="add-equipment-button"
                    className="text-xs flex items-center gap-1 px-3 py-1.5 bg-[#1D4ED8] text-white hover:bg-[#1E40AF] disabled:opacity-50">
                    <Plus size={12} /> Add equipment
                </button>
            </div>
            <div className="divide-y divide-slate-200">
                {props.length === 0 && <div className="p-6 text-sm text-slate-500 text-center">Add a property first to track equipment.</div>}
                {items.length === 0 && props.length > 0 && <div className="p-6 text-sm text-slate-500 text-center">No equipment yet.</div>}
                {items.map((e) => {
                    const prop = props.find((p) => p.id === e.property_id);
                    return (
                        <div key={e.id} className="p-4 flex items-center gap-3" data-testid={`equipment-row-${e.id}`}>
                            <Wrench size={18} className="text-slate-400 shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="font-medium">{e.kind} {e.brand && `· ${e.brand}`} {e.model && `· ${e.model}`}</div>
                                <div className="text-xs text-slate-500 truncate">
                                    {prop?.nickname || prop?.address || "—"}
                                    {e.serial && ` · SN ${e.serial}`}
                                    {e.install_date && ` · installed ${e.install_date}`}
                                </div>
                            </div>
                            <button onClick={() => remove(e.id)} className="text-xs text-[#DC2626] hover:underline inline-flex items-center gap-1"><Trash size={12} /> Remove</button>
                        </div>
                    );
                })}
            </div>
            {open && <EquipmentModal customerId={customerId} props={props} onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />}
        </section>
    );
}

function EquipmentModal({ customerId, props, onClose, onSaved }) {
    const [form, setForm] = useState({
        property_id: props[0]?.id || "", kind: "AC", brand: "", model: "", serial: "", install_date: "", warranty_until: "",
    });
    const [saving, setSaving] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post(`/customers/${customerId}/equipment`, form);
            toast.success("Equipment added"); onSaved();
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
        finally { setSaving(false); }
    };
    return (
        <Modal title="Add equipment" onClose={onClose}>
            <form onSubmit={submit} className="p-6 space-y-3">
                <select value={form.property_id} onChange={(e) => setForm({...form, property_id: e.target.value})}
                    data-testid="equipment-property-select" required
                    className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                    {props.map((p) => <option key={p.id} value={p.id}>{p.nickname || p.address}</option>)}
                </select>
                <div className="grid grid-cols-2 gap-3">
                    <select value={form.kind} onChange={(e) => setForm({...form, kind: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                        {["AC","Furnace","Heat Pump","Water Heater","Garage Door","Panel","Boiler","Generator","Other"].map((k) => <option key={k}>{k}</option>)}
                    </select>
                    <input placeholder="Brand" value={form.brand} onChange={(e) => setForm({...form, brand: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                    <input placeholder="Model" value={form.model} onChange={(e) => setForm({...form, model: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <input placeholder="Serial" value={form.serial} onChange={(e) => setForm({...form, serial: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                    <input type="date" value={form.install_date} onChange={(e) => setForm({...form, install_date: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                    <input type="date" value={form.warranty_until} onChange={(e) => setForm({...form, warranty_until: e.target.value})}
                        className="w-full border border-slate-300 px-3 py-2.5" />
                </div>
                <button type="submit" disabled={saving} data-testid="equipment-submit-button"
                    className="w-full bg-[#1D4ED8] text-white py-2.5 font-semibold hover:bg-[#1E40AF] disabled:opacity-60">
                    {saving ? "Saving..." : "Add"}
                </button>
            </form>
        </Modal>
    );
}

function TimelineTab({ events }) {
    if (events.length === 0) return <div className="p-6 text-sm text-slate-500 text-center border border-slate-200">No history yet.</div>;
    const ICON = { job: Wrench, comm: ChatCircle, file: Paperclip };
    return (
        <ol className="relative border-l-2 border-slate-200 ml-4 space-y-6 pl-6">
            {events.map((e) => {
                const Icon = ICON[e.kind] || ClockCounterClockwise;
                return (
                    <li key={e.ref || e.ts} className="relative" data-testid={`timeline-${e.kind}`}>
                        <span className="absolute -left-[34px] -top-1 h-7 w-7 bg-white border-2 border-slate-200 flex items-center justify-center">
                            <Icon size={12} className="text-slate-500" />
                        </span>
                        <div className="text-xs text-slate-400 font-mono">{e.ts ? new Date(e.ts).toLocaleString() : ""}</div>
                        <div className="font-medium text-slate-900 mt-0.5">{e.title || e.summary}</div>
                        {e.kind === "job" && (
                            <div className="text-xs text-slate-500 mt-0.5">
                                Status: {e.status} {e.price ? ` · $${(e.price || 0).toFixed(0)}` : ""}
                            </div>
                        )}
                        {e.kind === "comm" && e.actor && (<div className="text-xs text-slate-500 mt-0.5">{e.actor}</div>)}
                    </li>
                );
            })}
        </ol>
    );
}

function FilesTab({ customerId, files, reload }) {
    const upload = async (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        const fd = new FormData(); fd.append("file", f);
        try {
            await api.post(`/customers/${customerId}/files`, fd, { headers: { "Content-Type": "multipart/form-data" }});
            toast.success("Uploaded"); reload();
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
        e.target.value = "";
    };
    const remove = async (fid) => {
        if (!window.confirm("Delete file?")) return;
        await api.delete(`/customers/${customerId}/files/${fid}`); toast.success("Deleted"); reload();
    };
    return (
        <section className="border border-slate-200">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                <div className="overline">Files · {files.length}</div>
                <label className="text-xs flex items-center gap-1 px-3 py-1.5 bg-[#1D4ED8] text-white hover:bg-[#1E40AF] cursor-pointer" data-testid="file-upload-label">
                    <UploadSimple size={12} /> Upload
                    <input type="file" onChange={upload} className="hidden" data-testid="file-upload-input" />
                </label>
            </div>
            <div className="divide-y divide-slate-200">
                {files.length === 0 && <div className="p-6 text-sm text-slate-500 text-center">No files yet.</div>}
                {files.map((f) => (
                    <div key={f.id} className="p-4 flex items-center gap-3" data-testid={`file-row-${f.id}`}>
                        <Paperclip size={16} className="text-slate-400 shrink-0" />
                        <a href={`${API_BASE}/files/${f.path}`} target="_blank" rel="noopener noreferrer"
                            className="flex-1 min-w-0 text-sm font-medium hover:text-[#1D4ED8] truncate">{f.filename}</a>
                        <span className="text-xs text-slate-400">{(f.size / 1024).toFixed(0)} KB</span>
                        <button onClick={() => remove(f.id)} className="text-xs text-[#DC2626] hover:underline">Remove</button>
                    </div>
                ))}
            </div>
        </section>
    );
}

function Modal({ title, onClose, children }) {
    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-md border border-slate-300" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                    <h2 className="font-display text-2xl font-extrabold tracking-tighter">{title}</h2>
                    <button onClick={onClose}><X size={20} /></button>
                </div>
                {children}
            </div>
        </div>
    );
}
