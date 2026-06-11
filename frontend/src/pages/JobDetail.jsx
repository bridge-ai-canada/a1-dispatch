import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api, { API_BASE, formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import {
    ArrowLeft, Camera, Trash, CreditCard, FloppyDisk, PencilSimple, Eraser,
    MapPin, Phone, Clock, CheckCircle, PlayCircle, UploadSimple,
    Bank, Copy, ChatText, X,
} from "@phosphor-icons/react";
import { AIPolishButton, AIActionButton } from "../components/AIAssist";
import JobChecklistPanel from "../components/JobChecklistPanel";

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
    const [showFinance, setShowFinance] = useState(false);
    const [financeResult, setFinanceResult] = useState(null);

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
                    {!job.paid && job.price >= 4500 && (
                        <button onClick={() => { setFinanceResult(null); setShowFinance(true); }} data-testid="detail-finance-button"
                            className="flex items-center gap-1.5 px-4 py-2.5 border border-violet-500 text-violet-700 hover:bg-violet-50 font-semibold">
                            <Bank size={16} /> Finance this job
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
                            <div className="flex items-center gap-3">
                                <AIPolishButton notes={notes} onPolished={(p) => setNotes(p)} />
                                {job.status === "completed" && (
                                    <AIActionButton label="Job summary"
                                        endpoint="/ai/jobs/summarize"
                                        body={{ job_id: id }}
                                        onResult={(d) => { setNotes(d.summary || notes); toast.success("Summary inserted"); }} />
                                )}
                                <button onClick={saveNotes} disabled={savingNotes} data-testid="save-notes-button"
                                    className="text-xs flex items-center gap-1 px-3 py-1.5 bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-60">
                                    <FloppyDisk size={12} /> {savingNotes ? "Saving..." : "Save"}
                                </button>
                            </div>
                        </div>
                        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={6}
                            data-testid="notes-textarea"
                            placeholder="Add diagnostic notes, parts used, customer remarks..."
                            className="w-full p-4 outline-none resize-y border-0 focus:ring-2 focus:ring-inset focus:ring-[#1D4ED8]" />
                    </section>

                    <UpsellSuggestion jobId={id} />

                    <JobChecklistPanel job={job} onChange={setJob} />

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

            {showFinance && (
                <FinanceJobModal job={job} onClose={() => setShowFinance(false)} result={financeResult} setResult={setFinanceResult} />
            )}
        </div>
    );
}

function FinanceJobModal({ job, onClose, result, setResult }) {
    const [term, setTerm] = useState(60);
    const [amount, setAmount] = useState(job.price || 0);
    const [creating, setCreating] = useState(false);
    const [sending, setSending] = useState(false);
    const [programs, setPrograms] = useState([]);
    const [programId, setProgramId] = useState("");
    const [quote, setQuote] = useState(null);

    useEffect(() => {
        api.get("/financing/programs", { params: { active: true } })
            .then(({ data }) => setPrograms(data))
            .catch(() => {});
    }, []);

    useEffect(() => {
        if (!programId || !amount) { setQuote(null); return; }
        api.post("/financing/program-quote", { amount: Number(amount), program_id: programId })
            .then(({ data }) => setQuote(data))
            .catch(() => setQuote(null));
    }, [programId, amount]);

    const create = async (sendSms = false) => {
        const setter = sendSms ? setSending : setCreating;
        setter(true);
        try {
            const { data } = await api.post("/financing/from-job", {
                job_id: job.id,
                amount: Number(amount),
                term_months: Number(term),
                program_id: programId || undefined,
                send_sms: sendSms,
                origin_url: window.location.origin,
            });
            setResult(data);
            if (sendSms) {
                if (data.sms_result?.ok) toast.success(`Text sent to ${job.customer_phone}`);
                else if (data.sms_result?.error === "twilio_not_configured") toast.error("Twilio not configured — copy the link to share manually.");
                else if (data.sms_result?.error === "no_customer_phone") toast.error("Customer has no phone on file.");
                else if (data.sms_result?.error) toast.error(`SMS failed: ${data.sms_result.error}`);
                else toast.success("Application created");
            } else {
                toast.success("Application created");
            }
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setter(false); }
    };

    const publicUrl = result ? `${window.location.origin}/finance/${result.public_token}` : "";
    const copy = () => {
        navigator.clipboard.writeText(publicUrl).catch(() => {});
        toast.success("Link copied");
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-50 grid place-items-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="finance-job-modal">
                <div className="flex items-center justify-between">
                    <h2 className="font-bold text-lg flex items-center gap-2"><Bank size={20}/> Finance this job</h2>
                    <button onClick={onClose}><X size={20}/></button>
                </div>
                {!result && (
                    <>
                        <p className="text-sm text-slate-500">Create a Fresh Cash application for <strong>{job.customer_name}</strong>.</p>
                        <label className="text-xs block">Program
                            <select value={programId} onChange={(e) => setProgramId(e.target.value)}
                                className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="finance-job-program">
                                <option value="">— Default (Fresh Cash decisioning) —</option>
                                {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                            </select>
                        </label>
                        <div className="grid grid-cols-2 gap-3">
                            <label className="text-xs block">Amount ($)
                                <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
                                    className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="finance-job-amount"/>
                            </label>
                            <label className="text-xs block">Term (months)
                                <select value={term} onChange={(e) => setTerm(e.target.value)} className="w-full h-10 px-3 rounded border border-slate-300 text-sm mt-1" data-testid="finance-job-term">
                                    {[12, 24, 36, 48, 60, 72, 84, 120].map((t) => <option key={t}>{t}</option>)}
                                </select>
                            </label>
                        </div>
                        {quote && (
                            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs space-y-1" data-testid="finance-job-quote">
                                <div className="flex justify-between"><span className="text-slate-600">Customer pays:</span><span className="font-mono font-bold">${quote.monthly_payment}/mo</span></div>
                                <div className="flex justify-between"><span className="text-slate-600">Your net payout:</span><span className="font-mono font-bold text-emerald-700">${quote.net_payout.toLocaleString()}</span></div>
                                <div className="flex justify-between"><span className="text-slate-600">Dealer fee:</span><span className="font-mono">${quote.contractor_fee_dollars} ({quote.dealer_fee_pct}%)</span></div>
                            </div>
                        )}
                        <div className="bg-violet-50 border border-violet-200 rounded-lg px-3 py-2 text-xs text-violet-900">
                            Soft credit check only — won't affect their score.
                        </div>
                        <div className="flex gap-2">
                            <button onClick={() => create(false)} disabled={creating || sending || !amount}
                                className="flex-1 px-4 py-3 rounded-xl border border-slate-300 hover:bg-slate-50 font-bold text-sm disabled:opacity-50" data-testid="finance-job-create">
                                {creating ? "…" : "Create link"}
                            </button>
                            <button onClick={() => create(true)} disabled={creating || sending || !amount || !job.customer_phone}
                                className="flex-1 px-4 py-3 rounded-xl bg-violet-700 text-white font-bold text-sm disabled:opacity-50 inline-flex items-center justify-center gap-1" data-testid="finance-job-create-sms">
                                <ChatText size={14}/> {sending ? "Sending…" : `Text ${job.customer_phone ? "now" : "(no #)"}`}
                            </button>
                        </div>
                    </>
                )}
                {result && (
                    <div className="space-y-3" data-testid="finance-job-result">
                        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                            <div className="text-sm font-bold text-green-900 flex items-center gap-1"><CheckCircle size={14} weight="fill"/> Application created</div>
                            <div className="text-xs text-green-700 mt-1">${result.amount} · {result.term_months} months</div>
                        </div>
                        <div>
                            <div className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Customer link</div>
                            <div className="flex gap-1">
                                <code className="flex-1 truncate bg-slate-50 px-2 py-2 rounded border text-xs">{publicUrl}</code>
                                <button onClick={copy} className="px-2 rounded border border-slate-300 hover:bg-slate-50" data-testid="finance-job-copy"><Copy size={14}/></button>
                            </div>
                        </div>
                        <a href={publicUrl} target="_blank" rel="noreferrer" className="block w-full text-center px-4 py-3 rounded-xl bg-violet-700 text-white font-bold text-sm">
                            Open customer view →
                        </a>
                    </div>
                )}
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

function UpsellSuggestion({ jobId }) {
    const [busy, setBusy] = useState(false);
    const [result, setResult] = useState(null);
    const run = async () => {
        setBusy(true);
        try {
            const { data } = await api.post("/ai/jobs/upsell", { job_id: jobId }, { timeout: 60_000 });
            setResult(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(false); }
    };
    return (
        <section className="border-2 border-dashed border-[#F97316]/50 bg-orange-50/30 p-4 rounded-lg">
            {!result ? (
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <div className="text-xs font-bold uppercase tracking-widest text-[#F97316]">✨ AI upsell suggestion</div>
                        <p className="mt-1 text-sm text-slate-600">Generate a personalized upsell recommendation for this customer.</p>
                    </div>
                    <button onClick={run} disabled={busy}
                        className="bg-[#F97316] hover:bg-[#EA580C] text-white font-bold text-sm px-4 py-2 rounded-lg disabled:opacity-50"
                        data-testid="ai-upsell-button">
                        {busy ? "Thinking…" : "Get suggestion"}
                    </button>
                </div>
            ) : (
                <div>
                    <div className="text-xs font-bold uppercase tracking-widest text-[#F97316]">✨ Recommended upsell</div>
                    <div className="mt-1 flex items-baseline justify-between gap-3">
                        <div className="text-lg font-extrabold text-slate-900">{result.title}</div>
                        {result.suggested_price > 0 && (
                            <div className="text-lg font-extrabold text-emerald-600">${Number(result.suggested_price).toFixed(2)}</div>
                        )}
                    </div>
                    <p className="mt-1 text-sm text-slate-700">{result.reason}</p>
                    {result.confidence != null && (
                        <div className="mt-2 text-xs text-slate-500">
                            Confidence: <b>{(result.confidence * 100).toFixed(0)}%</b>
                        </div>
                    )}
                    <button onClick={() => setResult(null)} className="mt-2 text-xs text-slate-500 hover:text-slate-900">
                        Try another
                    </button>
                </div>
            )}
        </section>
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
