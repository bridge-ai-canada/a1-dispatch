import { useState, useRef, useEffect } from "react";
import api, { formatApiError } from "../lib/api";
import { Sparkle, X, PaperPlaneTilt } from "@phosphor-icons/react";
import { toast } from "sonner";

/**
 * AIDispatcherPanel — floating "Ask AI" widget that lives on the Dispatch page.
 * Click the orange button to open; ask natural-language questions about scheduling.
 */
export default function AIDispatcherPanel() {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const [sessionId, setSessionId] = useState(null);
    const endRef = useRef(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const send = async () => {
        const text = input.trim();
        if (!text) return;
        setMessages((m) => [...m, { role: "user", text }]);
        setInput("");
        setBusy(true);
        try {
            const { data } = await api.post("/ai/dispatcher/ask", {
                question: text, session_id: sessionId,
            }, { timeout: 60_000 });
            setSessionId(data.session_id);
            setMessages((m) => [...m, { role: "assistant", text: data.answer }]);
        } catch (e) {
            toast.error(formatApiError(e.response?.data?.detail));
        } finally { setBusy(false); }
    };

    return (
        <>
            <button onClick={() => setOpen(true)}
                className="fixed bottom-6 right-6 z-40 bg-gradient-to-r from-[#F97316] to-[#EA580C] text-white rounded-full p-4 shadow-xl hover:shadow-2xl hover:scale-105 transition"
                data-testid="ai-dispatcher-open">
                <Sparkle size={24} weight="fill"/>
            </button>

            {open && (
                <div className="fixed bottom-6 right-6 z-50 w-96 max-w-[calc(100vw-2rem)] h-[36rem] max-h-[calc(100vh-3rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col">
                    <header className="px-4 py-3 bg-gradient-to-r from-[#F97316] to-[#EA580C] text-white rounded-t-2xl flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Sparkle size={18} weight="fill"/>
                            <div>
                                <div className="font-bold text-sm">AI Dispatcher</div>
                                <div className="text-[10px] opacity-90">Ask me anything about scheduling</div>
                            </div>
                        </div>
                        <button onClick={() => setOpen(false)} className="p-1 hover:bg-white/20 rounded">
                            <X size={18}/>
                        </button>
                    </header>

                    <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
                        {messages.length === 0 && (
                            <div className="text-xs text-slate-500 space-y-2">
                                <div className="font-semibold text-slate-700">Try asking:</div>
                                {[
                                    "Who's free in Austin tomorrow at 2pm?",
                                    "What's our busiest day this week?",
                                    "Which jobs are unassigned right now?",
                                ].map((q) => (
                                    <button key={q} onClick={() => setInput(q)}
                                        className="block w-full text-left bg-white border border-slate-200 hover:border-[#F97316] hover:text-[#F97316] rounded-lg px-3 py-2 transition">
                                        {q}
                                    </button>
                                ))}
                            </div>
                        )}
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm ${
                                    m.role === "user"
                                        ? "bg-slate-900 text-white rounded-br-md"
                                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-md"
                                }`}>
                                    {m.text}
                                </div>
                            </div>
                        ))}
                        {busy && (
                            <div className="flex justify-start">
                                <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-3 py-2 text-sm text-slate-500">
                                    <span className="inline-block animate-pulse">●●●</span>
                                </div>
                            </div>
                        )}
                        <div ref={endRef} />
                    </div>

                    <div className="p-3 border-t border-slate-200">
                        <div className="flex items-center gap-2">
                            <input value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && !busy && send()}
                                placeholder="Ask about scheduling…"
                                className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#F97316]"
                                data-testid="ai-dispatcher-input"/>
                            <button onClick={send} disabled={busy || !input.trim()}
                                className="bg-[#F97316] hover:bg-[#EA580C] disabled:opacity-50 text-white p-2 rounded-lg"
                                data-testid="ai-dispatcher-send">
                                <PaperPlaneTilt size={18} weight="fill"/>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
