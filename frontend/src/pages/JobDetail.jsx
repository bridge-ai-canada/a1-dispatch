import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api, { API_BASE, formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
    ArrowLeft, Camera, Trash, CreditCard, FloppyDisk, PencilSimple, Eraser,
    MapPin, Phone, Clock, CheckCircle, PlayCircle, UploadSimple,
} from "@phosphor-icons/react";

const STATUS_NEXT = {
    unscheduled: { label: "Schedule", next: "scheduled_installation" },
    won_bid: { label: "Schedule", next: "scheduled_installation" },
    on_hold: { label: "Resume", next: "scheduled_installation" },
    scheduled_installation: { label: "Start Job", next: "in_progress" },
    scheduled: { label: "Start Job", next: "in_progress" }, // legacy fallback
    in_progress: { label: "Mark Complete", next: "completed" },
};

function fileUrl(path) {
    return `${API_BASE}/files/${path}`;
}

export default function JobDetail() {
    const { id } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();
    const [job, setJob] = useState(null);
    const [notes, setNotes] = useState("");
    const [savingNotes, setSavingNotes] = useState(false);
    const [team, setTeam] = useState([]);

    const load = () => {
        api.get(`/jobs/${id}`).then((r) => { setJob(r.data); setNotes(r.data.description || ""); });
        api.get("/team").then((r) => setTeam(r.data));
    };
    useEffect(() => { load(); }, [id]); // eslint-disable-line

    if (!job) return <div className="p-8 text-slate-500">Loading...</div>;

    const updateJob = async (patch) => {
        try {
            const { data } = await api.patch(`/jobs/${id}`, patch);
            setJob(data);
            return data;
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    const saveNotes = async () => {
        setSavingNotes(true);
        await updateJob({ description: notes });
        toast.success("Notes saved");
        setSavingNotes(false);
    };

    const advance = async () => {
        const next = STATUS_NEXT[job.status]?.next;
        if (!next) return;
        await updateJob({ status: next });
        toast.success(`Marked ${next.replace("_"," ")}`);
    };

    const uploadPhoto = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const fd = new FormData();
        fd.append("file", file);
        try {
            await api.post(`/jobs/${id}/photos`, fd, { headers: { "Content-Type": "multipart/form-data" }});
            toast.success("Photo uploaded");
            load();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
        e.target.value = "";
    };

    const removePhoto = async (pid) => {
        if (!window.confirm("Remove this photo?")) return;
        await api.delete(`/jobs/${id}/photos/${pid}`);
        load();
    };

    const charge = async () => {
        try {
            const { data } = await api.post("/payments/checkout", { job_id: id, origin_url: window.location.origin });
            window.location.href = data.url;
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    const tech = team.find((t) => t.id === job.assigned_to);

    return (
        <div data-testid="job-detail-page" className="space-y-6 max-w-5xl">
            <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900">
                <ArrowLeft size={16} /> Back
            </button>

            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Work Order · {job.job_type}</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1" data-testid="job-detail-title">{job.title}</h1>
                </div>
                <div className="flex items-center gap-2">
                    <a href={`${API_BASE}/jobs/${id}/invoice.pdf`}
                        target="_blank" rel="noopener noreferrer"
                        data-testid="download-invoice-button"
                        className="flex items-center gap-1.5 px-4 py-2.5 border border-slate-300 hover:bg-slate-50 font-semibold text-sm">
                        Invoice PDF
                    </a>
                    {!job.paid && job.price > 0 && (
                        <button onClick={charge} data-testid="detail-charge-button"
                            className="flex items-center gap-1.5 px-4 py-2.5 border border-emerald-500 text-emerald-700 hover:bg-emerald-50 font-semibold">
                            <CreditCard size={16} /> Charge ${job.price.toFixed(0)}
                        </button>
                    )}
                    {STATUS_NEXT[job.status] && (
                        <button onClick={advance} data-testid="detail-advance-status-button"
                            className="flex items-center gap-1.5 px-4 py-2.5 bg-[#1D4ED8] text-white hover:bg-[#1E40AF] font-semibold">
                            {job.status === "in_progress" ? <CheckCircle size={16} weight="fill" /> : <PlayCircle size={16} weight="fill" />}
                            {STATUS_NEXT[job.status].label}
                        </button>
                    )}
                </div>
            </div>

            <div className="grid lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                    <section className="border border-slate-200 p-5">
                        <div className="overline mb-3">Customer & Schedule</div>
                        <div className="grid sm:grid-cols-2 gap-y-3 text-sm">
                            <Info label="Customer" value={job.customer_name} />
                            <Info label="Phone" value={job.customer_phone} icon={Phone} />
                            <Info label="Address" value={job.address} icon={MapPin} className="sm:col-span-2" />
                            <Info label="Scheduled" icon={Clock}
                                value={job.scheduled_at ? new Date(job.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "—"} />
                            <Info label="Technician" value={tech?.name || "Unassigned"} />
                            <Info label="Price" value={`$${(job.price || 0).toFixed(2)}`} />
                            <Info label="Status" value={job.status.replace("_"," ")} />
                        </div>
                    </section>

                    <section className="border border-slate-200">
                        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                            <div className="overline">Notes</div>
                            <button onClick={saveNotes} disabled={savingNotes} data-testid="save-notes-button"
                                className="text-xs flex items-center gap-1 px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-60">
                                <FloppyDisk size={12} /> {savingNotes ? "Saving..." : "Save"}
                            </button>
                        </div>
                        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={6}
                            data-testid="notes-textarea"
                            placeholder="Add diagnostic notes, parts used, customer remarks..."
                            className="w-full p-4 outline-none resize-y border-0 focus:ring-2 focus:ring-inset focus:ring-[#1D4ED8]" />
                    </section>

                    <section className="border border-slate-200">
                        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                            <div className="overline">Photos · {job.photos?.length || 0}</div>
                            <label data-testid="upload-photo-label" className="cursor-pointer text-xs flex items-center gap-1 px-3 py-1.5 bg-[#1D4ED8] text-white hover:bg-[#1E40AF]">
                                <Camera size={12} /> Upload
                                <input type="file" accept="image/*" onChange={uploadPhoto} className="hidden" data-testid="upload-photo-input" />
                            </label>
                        </div>
                        <div className="p-5 grid grid-cols-2 sm:grid-cols-3 gap-3">
                            {(job.photos || []).length === 0 && (
                                <div className="col-span-full text-center text-sm text-slate-500 py-8">No photos yet.</div>
                            )}
                            {(job.photos || []).map((p) => (
                                <div key={p.id} className="relative group border border-slate-200">
                                    <img src={fileUrl(p.path)} alt="" className="w-full h-32 object-cover" />
                                    <button onClick={() => removePhoto(p.id)} data-testid={`remove-photo-${p.id}`}
                                        className="absolute top-1 right-1 h-7 w-7 bg-white/90 hover:bg-[#DC2626] hover:text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Trash size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </section>
                </div>

                <div className="space-y-6">
                    <SignaturePad job={job} onSaved={load} />
                </div>
            </div>
        </div>
    );
}

function Info({ label, value, icon: Icon, className = "" }) {
    return (
        <div className={className}>
            <div className="overline mb-0.5">{label}</div>
            <div className="font-medium text-slate-900 flex items-center gap-1.5">
                {Icon && <Icon size={14} className="text-slate-400" />}
                {value || "—"}
            </div>
        </div>
    );
}

function SignaturePad({ job, onSaved }) {
    const canvasRef = useRef(null);
    const drawing = useRef(false);
    const [signerName, setSignerName] = useState("");
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        const cvs = canvasRef.current;
        if (!cvs) return;
        const ctx = cvs.getContext("2d");
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, cvs.width, cvs.height);
        ctx.strokeStyle = "#0f172a";
        ctx.lineWidth = 2.5;
        ctx.lineCap = "round";
    }, []);

    const pos = (e) => {
        const cvs = canvasRef.current;
        const r = cvs.getBoundingClientRect();
        const t = e.touches?.[0];
        const x = ((t ? t.clientX : e.clientX) - r.left) * (cvs.width / r.width);
        const y = ((t ? t.clientY : e.clientY) - r.top) * (cvs.height / r.height);
        return { x, y };
    };
    const start = (e) => { e.preventDefault(); drawing.current = true; const ctx = canvasRef.current.getContext("2d"); const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); };
    const move  = (e) => { if (!drawing.current) return; e.preventDefault(); const ctx = canvasRef.current.getContext("2d"); const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); };
    const end   = () => { drawing.current = false; };

    const clear = () => {
        const cvs = canvasRef.current;
        const ctx = cvs.getContext("2d");
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, cvs.width, cvs.height);
    };

    const save = async () => {
        setSaving(true);
        try {
            const dataUrl = canvasRef.current.toDataURL("image/png");
            await api.post(`/jobs/${job.id}/signature`, { image_base64: dataUrl, signer_name: signerName });
            toast.success("Signature captured");
            onSaved();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        } finally {
            setSaving(false);
        }
    };

    return (
        <section className="border border-slate-200">
            <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
                <div className="overline">Signature</div>
                {job.signature && (
                    <span className="text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-700 font-semibold uppercase tracking-wider">Signed</span>
                )}
            </div>
            {job.signature ? (
                <div className="p-5 space-y-3">
                    <img src={fileUrl(job.signature.path)} alt="signature" className="w-full bg-white border border-slate-200" />
                    <div className="text-sm">
                        <div className="font-medium">{job.signature.signer_name || "Signed"}</div>
                        <div className="text-xs text-slate-500 mt-0.5">{new Date(job.signature.signed_at).toLocaleString()}</div>
                    </div>
                    <button onClick={() => { /* allow re-sign */ }} className="hidden" />
                </div>
            ) : (
                <div className="p-5 space-y-3">
                    <input value={signerName} onChange={(e) => setSignerName(e.target.value)}
                        placeholder="Signer name" data-testid="signer-name-input"
                        className="w-full border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    <canvas ref={canvasRef} width={600} height={200}
                        data-testid="signature-canvas"
                        className="w-full bg-white border border-dashed border-slate-400 touch-none"
                        onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
                        onTouchStart={start} onTouchMove={move} onTouchEnd={end} />
                    <div className="flex gap-2">
                        <button onClick={clear} data-testid="clear-signature-button"
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 border border-slate-300 hover:bg-slate-50 text-sm">
                            <Eraser size={14} /> Clear
                        </button>
                        <button onClick={save} disabled={saving} data-testid="save-signature-button"
                            className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-[#DC2626] text-white hover:bg-[#B91C1C] disabled:opacity-60 text-sm font-semibold">
                            <PencilSimple size={14} /> {saving ? "Saving..." : "Save"}
                        </button>
                    </div>
                </div>
            )}
        </section>
    );
}
