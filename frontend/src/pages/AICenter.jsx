import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import {
    Sparkle, Lightning, ChatCircleText, CalendarBlank, Receipt, MagicWand,
    Confetti, Wrench, Phone, X, ArrowSquareOut,
} from "@phosphor-icons/react";
import { Link } from "react-router-dom";

function fmtTime(iso) { return new Date(iso).toLocaleString(); }

const FEATURES = [
    { icon: MagicWand, label: "Estimate generator",
      blurb: "Generates Good/Better/Best tiers from a description.",
      cta: "Try it", to: "/app/estimates/new" },
    { icon: Phone, label: "Call summaries",
      blurb: "Structures raw call notes into action items.",
      cta: "Open customers", to: "/app/customers" },
    { icon: Wrench, label: "Tech notes polish & job summary",
      blurb: "Rewrites rough field notes into invoice-ready prose.",
      cta: "Open jobs", to: "/app/jobs" },
    { icon: Lightning, label: "Dispatcher assistant",
      blurb: "Ask scheduling questions in plain English.",
      cta: "Open dispatch", to: "/app/dispatch" },
    { icon: ChatCircleText, label: "Customer chatbot",
      blurb: "Lives on your booking page. Handles sales + support.",
      cta: "View booking widget", to: "/app/companies" },
    { icon: Confetti, label: "Upsell recommendations",
      blurb: "One-click suggestions in each job card.",
      cta: "Open jobs", to: "/app/jobs" },
];

export default function AICenter() {
    const [maint, setMaint] = useState([]);
    const [logs, setLogs] = useState([]);
    const [busy, setBusy] = useState(false);
    const [tab, setTab] = useState("overview");

    const load = async () => {
        try {
            const [m, l] = await Promise.all([
                api.get("/ai/maintenance/suggestions"),
                api.get("/ai/logs?limit=30"),
            ]);
            setMaint(m.data || []);
            setLogs(l.data || []);
        } catch (e) { /* tolerate */ }
    };
    useEffect(() => { load(); }, []);

    const scan = async () => {
        setBusy(true);
        try {
            const { data } = await api.post("/ai/maintenance/scan", { limit: 50 }, { timeout: 180_000 });
            toast.success(`Scanned ${data.scanned} customers — ${data.suggested} due for service`);
            load();
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setBusy(false); }
    };

    const dismiss = async (id) => {
        await api.post(`/ai/maintenance/${id}/dismiss`);
        setMaint((items) => items.filter((m) => m.id !== id));
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-[#F97316]">
                        <Sparkle size={12} weight="fill"/> AI-powered
                    </div>
                    <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-slate-900">AI Assistant</h1>
                    <p className="text-sm text-slate-500">Reduce office workload and improve sales conversions.</p>
                </div>
            </div>

            <div className="flex items-center gap-2">
                {["overview", "maintenance", "logs"].map((t) => (
                    <button key={t} onClick={() => setTab(t)}
                        className={`px-3 py-1.5 text-sm font-medium rounded-full border transition ${
                            tab === t ? "bg-slate-900 text-white border-slate-900"
                                : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
                        }`}
                        data-testid={`ai-tab-${t}`}>
                        {t === "overview" ? "Overview"
                            : t === "maintenance" ? `Maintenance (${maint.length})`
                            : "Activity log"}
                    </button>
                ))}
            </div>

            {tab === "overview" && (
                <>
                    <div className="rounded-2xl border-2 border-dashed border-[#F97316]/50 bg-orange-50/30 p-6">
                        <div className="flex items-start gap-4">
                            <div className="bg-[#F97316] text-white p-3 rounded-2xl">
                                <Sparkle size={24} weight="fill"/>
                            </div>
                            <div className="flex-1">
                                <div className="text-xs font-bold uppercase tracking-widest text-[#F97316]">Powered by OpenAI</div>
                                <h2 className="mt-1 text-xl font-extrabold tracking-tight text-slate-900">
                                    8 AI features active across your app
                                </h2>
                                <p className="mt-1 text-sm text-slate-600">
                                    Every customer-facing flow is enhanced with intelligent assistance.
                                </p>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {FEATURES.map(({ icon: Icon, label, blurb, cta, to }) => (
                            <div key={label} className="rounded-2xl border border-slate-200 bg-white p-5 hover:border-[#F97316] transition">
                                <div className="inline-flex items-center justify-center bg-orange-50 text-[#F97316] w-10 h-10 rounded-xl">
                                    <Icon size={18} weight="bold"/>
                                </div>
                                <div className="mt-3 font-extrabold text-slate-900">{label}</div>
                                <p className="mt-1 text-sm text-slate-500">{blurb}</p>
                                <Link to={to} className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-[#F97316] hover:text-[#EA580C]">
                                    {cta} <ArrowSquareOut size={12} weight="bold"/>
                                </Link>
                            </div>
                        ))}
                    </div>

                    <div className="rounded-2xl border border-slate-200 bg-white p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-bold text-slate-900 flex items-center gap-2">
                                    <CalendarBlank size={18}/> Maintenance scanner
                                </h3>
                                <p className="text-sm text-slate-500">
                                    Scans your customer base and flags who's due for recurring service.
                                </p>
                            </div>
                            <button onClick={scan} disabled={busy}
                                className="inline-flex items-center gap-2 bg-[#F97316] hover:bg-[#EA580C] text-white font-bold text-sm px-4 py-2 rounded-lg disabled:opacity-50"
                                data-testid="ai-scan-maintenance-button">
                                <Sparkle size={14} weight="fill"/> {busy ? "Scanning…" : "Scan now"}
                            </button>
                        </div>
                    </div>
                </>
            )}

            {tab === "maintenance" && (
                <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                    {maint.length === 0 ? (
                        <div className="p-12 text-center">
                            <CalendarBlank size={48} className="mx-auto text-slate-300"/>
                            <p className="mt-3 text-slate-500">No suggestions yet. Run the scanner to surface customers due for service.</p>
                            <button onClick={scan} disabled={busy}
                                className="mt-4 inline-flex items-center gap-2 bg-[#F97316] hover:bg-[#EA580C] text-white font-bold text-sm px-4 py-2 rounded-lg disabled:opacity-50">
                                <Sparkle size={14} weight="fill"/> {busy ? "Scanning…" : "Scan now"}
                            </button>
                        </div>
                    ) : (
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                                <tr>
                                    <th className="text-left px-4 py-3">Customer</th>
                                    <th className="text-left px-4 py-3">Service</th>
                                    <th className="text-left px-4 py-3">Cadence</th>
                                    <th className="text-left px-4 py-3">Reason</th>
                                    <th className="text-right px-4 py-3"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {maint.map((m) => (
                                    <tr key={m.id} className="border-t border-slate-100">
                                        <td className="px-4 py-3 font-semibold">{m.customer_name}</td>
                                        <td className="px-4 py-3">{m.service_type}</td>
                                        <td className="px-4 py-3">
                                            <span className="inline-block px-2 py-0.5 rounded-full bg-orange-50 text-[#EA580C] text-xs font-bold uppercase">
                                                {m.cadence}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-slate-600 text-xs">{m.reason}</td>
                                        <td className="px-4 py-3 text-right">
                                            <button onClick={() => dismiss(m.id)}
                                                className="text-xs text-slate-400 hover:text-[#DC2626]">
                                                Dismiss
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

            {tab === "logs" && (
                <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
                    {logs.length === 0 ? (
                        <div className="p-12 text-center text-slate-500">No AI activity yet.</div>
                    ) : (
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                                <tr>
                                    <th className="text-left px-4 py-3">When</th>
                                    <th className="text-left px-4 py-3">Feature</th>
                                    <th className="text-left px-4 py-3">Model</th>
                                    <th className="text-right px-4 py-3">In</th>
                                    <th className="text-right px-4 py-3">Out</th>
                                    <th className="text-center px-4 py-3">OK</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map((l) => (
                                    <tr key={l.id} className="border-t border-slate-100">
                                        <td className="px-4 py-3 text-xs text-slate-500">{fmtTime(l.created_at)}</td>
                                        <td className="px-4 py-3 font-semibold">{l.feature}</td>
                                        <td className="px-4 py-3 text-xs text-slate-500">{l.model}</td>
                                        <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">{l.input_chars}c</td>
                                        <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">{l.output_chars}c</td>
                                        <td className="px-4 py-3 text-center">
                                            {l.success
                                                ? <span className="text-emerald-600 font-bold">✓</span>
                                                : <span className="text-[#DC2626] font-bold" title={l.error}>×</span>}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
        </div>
    );
}
