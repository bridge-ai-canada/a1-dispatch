import { useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Sparkle, X } from "@phosphor-icons/react";

/** Floating "Generate with AI" modal for the Estimate Builder.
 *  Calls /api/ai/estimates/generate and returns the {title,intro,tiers} payload
 *  via onGenerated. Parent owns deciding how to apply it to its form state.
 */
export function AIGenerateEstimateButton({ onGenerated }) {
    const [open, setOpen] = useState(false);
    const [prompt, setPrompt] = useState("");
    const [busy, setBusy] = useState(false);

    const generate = async () => {
        if (!prompt.trim()) return toast.error("Describe the job first");
        setBusy(true);
        try {
            const { data } = await api.post("/ai/estimates/generate", { prompt }, { timeout: 90_000 });
            if (!data.tiers?.length) throw new Error("AI returned no tiers");
            onGenerated(data);
            toast.success("AI proposal applied — review and tweak before sending");
            setOpen(false);
            setPrompt("");
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail || e.message));
        } finally {
            setBusy(false);
        }
    };

    return (
        <>
            <button onClick={() => setOpen(true)}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-[#F97316] to-[#EA580C] text-white px-4 py-2.5 rounded-lg shadow-sm font-semibold text-sm hover:brightness-110 transition"
                data-testid="ai-generate-estimate-button">
                <Sparkle size={16} weight="fill"/> Generate with AI
            </button>

            {open && (
                <div className="fixed inset-0 bg-slate-900/60 z-50 flex items-end sm:items-center justify-center p-2 sm:p-4">
                    <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl">
                        <div className="flex items-start justify-between">
                            <div>
                                <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-[#F97316]">
                                    <Sparkle size={12} weight="fill"/> AI estimate
                                </div>
                                <h3 className="mt-1 text-2xl font-extrabold tracking-tight">Describe the job</h3>
                                <p className="mt-1 text-sm text-slate-500">
                                    Tell us what the customer said. We'll draft 3 Good/Better/Best tiers in seconds.
                                </p>
                            </div>
                            <button onClick={() => setOpen(false)} className="p-2 text-slate-400 hover:text-slate-700">
                                <X size={20}/>
                            </button>
                        </div>
                        <textarea autoFocus rows={5}
                            className="mt-4 w-full px-3 py-2 border border-slate-200 rounded-xl text-base"
                            placeholder="e.g. 12-year-old 3-ton AC, cooling poorly, 2400 sqft single-story home in Austin"
                            value={prompt} onChange={(e) => setPrompt(e.target.value)}
                            data-testid="ai-prompt-input"/>
                        <button onClick={generate} disabled={busy || !prompt.trim()}
                            className="mt-4 w-full inline-flex items-center justify-center gap-2 bg-[#F97316] hover:bg-[#EA580C] disabled:opacity-50 text-white font-bold py-4 rounded-xl text-base shadow-md transition"
                            data-testid="ai-generate-submit">
                            <Sparkle size={18} weight="fill"/> {busy ? "Drafting proposal…" : "Draft 3 tiers"}
                        </button>
                    </div>
                </div>
            )}
        </>
    );
}


/** Compact "Polish notes with AI" button — given current text, returns improved text. */
export function AIPolishButton({ notes, onPolished, endpoint = "/ai/tech-notes/polish", label = "Polish notes with AI" }) {
    const [busy, setBusy] = useState(false);
    const polish = async () => {
        if (!notes?.trim()) return toast.error("Add some notes first");
        setBusy(true);
        try {
            const { data } = await api.post(endpoint, { notes }, { timeout: 60_000 });
            onPolished(data.polished || data.summary || "");
            toast.success("AI polished your notes");
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setBusy(false); }
    };
    return (
        <button onClick={polish} disabled={busy}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#F97316] hover:text-[#EA580C] disabled:opacity-50"
            data-testid="ai-polish-button">
            <Sparkle size={12} weight="fill"/> {busy ? "Polishing…" : label}
        </button>
    );
}


/** Generic 1-click AI action button that POSTs a body and renders the response inline. */
export function AIActionButton({ label, endpoint, body, onResult, icon = true, className = "" }) {
    const [busy, setBusy] = useState(false);
    const run = async () => {
        setBusy(true);
        try {
            const { data } = await api.post(endpoint, body, { timeout: 60_000 });
            onResult(data);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setBusy(false); }
    };
    return (
        <button onClick={run} disabled={busy}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-[#F97316] to-[#EA580C] text-white text-xs font-bold shadow-sm hover:brightness-110 disabled:opacity-50 transition ${className}`}
            data-testid={`ai-action-${label.toLowerCase().replace(/\s+/g,'-')}`}>
            {icon && <Sparkle size={12} weight="fill"/>} {busy ? "Thinking…" : label}
        </button>
    );
}
