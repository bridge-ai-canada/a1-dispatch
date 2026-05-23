import { useEffect, useState, useMemo } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { EnvelopeSimple, ChatText, FloppyDisk, Eye, Code } from "@phosphor-icons/react";

export default function MessageTemplates() {
    const [templates, setTemplates] = useState([]);
    const [variables, setVariables] = useState([]);
    const [active, setActive] = useState(null);
    const [draft, setDraft] = useState({ subject: "", body: "", enabled: true });
    const [preview, setPreview] = useState(null);
    const [saving, setSaving] = useState(false);

    const load = async () => {
        try {
            const [{ data: t }, { data: v }] = await Promise.all([
                api.get("/message-templates"),
                api.get("/message-templates/variables"),
            ]);
            setTemplates(t);
            setVariables(v.variables || []);
            if (!active && t.length) {
                setActive(t[0].id);
                setDraft({ subject: t[0].subject || "", body: t[0].body, enabled: t[0].enabled });
            }
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { load(); }, []);

    const current = useMemo(() => templates.find((x) => x.id === active), [templates, active]);

    useEffect(() => {
        if (current) setDraft({ subject: current.subject || "", body: current.body, enabled: current.enabled });
    }, [current?.id]);

    const insertVar = (v) => {
        setDraft((d) => ({ ...d, body: `${d.body}${d.body.endsWith(" ") || !d.body ? "" : " "}$${v}` }));
    };

    const save = async () => {
        if (!current) return;
        setSaving(true);
        try {
            await api.patch(`/message-templates/${current.id}`, draft);
            toast.success("Template saved");
            await load();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setSaving(false); }
    };

    const doPreview = async () => {
        try {
            const { data } = await api.post("/message-templates/preview", { subject: draft.subject, body: draft.body });
            setPreview(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const emailTemplates = templates.filter((t) => t.kind === "email");
    const smsTemplates = templates.filter((t) => t.kind === "sms");

    return (
        <div className="space-y-5 max-w-7xl">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Message templates</h1>
                <p className="text-sm text-slate-500 mt-1">Customize the emails and SMS your customers receive. Use <code className="bg-slate-100 px-1 rounded">$variable</code> placeholders to inject data.</p>
            </header>

            <div className="grid lg:grid-cols-[280px_1fr] gap-5">
                {/* Sidebar list */}
                <aside className="space-y-4">
                    <div>
                        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-2"><EnvelopeSimple size={14}/> Email</div>
                        <div className="space-y-1">
                            {emailTemplates.map((t) => (
                                <button key={t.id} onClick={() => setActive(t.id)}
                                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${active === t.id ? "bg-[#1D4ED8] text-white font-bold" : "hover:bg-slate-100 text-slate-800"}`}
                                    data-testid={`tpl-${t.key}`}>
                                    {t.event.replace(/_/g, " ")}
                                    {!t.enabled && <span className="ml-2 text-[10px] opacity-70">(off)</span>}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-2"><ChatText size={14}/> SMS</div>
                        <div className="space-y-1">
                            {smsTemplates.map((t) => (
                                <button key={t.id} onClick={() => setActive(t.id)}
                                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${active === t.id ? "bg-[#1D4ED8] text-white font-bold" : "hover:bg-slate-100 text-slate-800"}`}
                                    data-testid={`tpl-${t.key}`}>
                                    {t.event.replace(/_/g, " ")}
                                </button>
                            ))}
                        </div>
                    </div>
                </aside>

                {/* Editor */}
                <main>
                    {!current ? (
                        <div className="text-slate-500 text-sm">Select a template to edit.</div>
                    ) : (
                        <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">{current.kind.toUpperCase()} · {current.event.replace(/_/g, " ")}</div>
                                    <div className="text-xs text-slate-500">Key: <code className="bg-slate-100 px-1 rounded">{current.key}</code></div>
                                </div>
                                <label className="inline-flex items-center gap-2 text-sm">
                                    <input type="checkbox" checked={draft.enabled} onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })} data-testid="tpl-enabled"/>
                                    Enabled
                                </label>
                            </div>

                            {current.kind === "email" && (
                                <label className="block">
                                    <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Subject</span>
                                    <input type="text" value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
                                        className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid="tpl-subject"/>
                                </label>
                            )}

                            <label className="block">
                                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Body</span>
                                <textarea value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                                    rows={current.kind === "sms" ? 4 : 12}
                                    className="mt-1 w-full px-3 py-2 rounded border border-slate-300 text-sm font-mono" data-testid="tpl-body"/>
                                {current.kind === "sms" && (
                                    <span className="text-xs text-slate-500 mt-1 block">{draft.body.length}/160 chars · long messages will be split into multiple segments by Twilio.</span>
                                )}
                            </label>

                            <div>
                                <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1"><Code size={12}/> Insert variable</div>
                                <div className="flex flex-wrap gap-1">
                                    {variables.map((v) => (
                                        <button key={v} onClick={() => insertVar(v)} className="text-xs font-mono px-2 py-1 rounded bg-slate-100 hover:bg-slate-200" data-testid={`tpl-var-${v}`}>${v}</button>
                                    ))}
                                </div>
                            </div>

                            <div className="flex gap-2">
                                <button onClick={doPreview} className="px-4 py-2 rounded-xl border border-slate-300 text-sm font-semibold inline-flex items-center gap-2" data-testid="tpl-preview-btn"><Eye size={14}/> Preview</button>
                                <button onClick={save} disabled={saving} className="ml-auto px-5 py-2 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm inline-flex items-center gap-2 disabled:opacity-50" data-testid="tpl-save-btn"><FloppyDisk size={14}/> {saving ? "Saving…" : "Save"}</button>
                            </div>

                            {preview && (
                                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2" data-testid="tpl-preview-box">
                                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Preview (with sample data)</div>
                                    {current.kind === "email" && preview.subject_rendered && (
                                        <div className="text-sm"><span className="font-bold">Subject:</span> {preview.subject_rendered}</div>
                                    )}
                                    <pre className="text-sm font-sans whitespace-pre-wrap text-slate-800">{preview.body_rendered}</pre>
                                </div>
                            )}
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
}
