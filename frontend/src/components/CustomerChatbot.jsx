import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Sparkle, X, PaperPlaneTilt, ChatCircleText } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SESSION_KEY = "a1.chatbot.sid";

/**
 * CustomerChatbot — embeddable floating chat widget for the public booking page.
 * Detects sales vs support intent via the AI prompt. No auth required.
 */
export default function CustomerChatbot({ companyId, companyName = "A1 Field Pro", primary = "#1D4ED8" }) {
    const [open, setOpen] = useState(false);
    const [messages, setMessages] = useState([
        { role: "assistant", text: `Hi! I'm ${companyName}'s assistant. How can I help today?` },
    ]);
    const [input, setInput] = useState("");
    const [busy, setBusy] = useState(false);
    const [sessionId, setSessionId] = useState(() => {
        try { return localStorage.getItem(SESSION_KEY) || null; }
        catch { return null; }
    });
    const endRef = useRef(null);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

    const send = async () => {
        const text = input.trim();
        if (!text) return;
        setMessages((m) => [...m, { role: "user", text }]);
        setInput("");
        setBusy(true);
        try {
            const { data } = await axios.post(`${API}/public/ai/chatbot`, {
                company_id: companyId, message: text, session_id: sessionId,
            }, { timeout: 60_000 });
            if (data.session_id) {
                setSessionId(data.session_id);
                try { localStorage.setItem(SESSION_KEY, data.session_id); } catch (_) {}
            }
            setMessages((m) => [...m, { role: "assistant", text: data.reply }]);
        } catch (e) {
            setMessages((m) => [...m, { role: "assistant", text: "Sorry, I'm having trouble. Please try again or call us." }]);
        } finally {
            setBusy(false);
        }
    };

    if (!companyId) return null;
    return (
        <>
            {!open && (
                <button onClick={() => setOpen(true)}
                    style={{ backgroundColor: primary }}
                    className="fixed bottom-5 right-5 z-40 text-white rounded-full px-5 py-3.5 shadow-xl hover:shadow-2xl hover:scale-105 transition inline-flex items-center gap-2 font-bold"
                    data-testid="chatbot-open">
                    <ChatCircleText size={20} weight="fill"/> Chat with us
                </button>
            )}
            {open && (
                <div className="fixed bottom-5 right-5 z-50 w-[22rem] max-w-[calc(100vw-2rem)] h-[32rem] max-h-[calc(100vh-2rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col">
                    <header style={{ backgroundColor: primary }}
                        className="px-4 py-3 text-white rounded-t-2xl flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Sparkle size={16} weight="fill"/>
                            <div>
                                <div className="font-bold text-sm">{companyName}</div>
                                <div className="text-[10px] opacity-90">AI-powered · Typically replies in seconds</div>
                            </div>
                        </div>
                        <button onClick={() => setOpen(false)} className="p-1 hover:bg-white/20 rounded">
                            <X size={18}/>
                        </button>
                    </header>

                    <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50">
                        {messages.map((m, i) => (
                            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-snug ${
                                    m.role === "user"
                                        ? "bg-slate-900 text-white rounded-br-md"
                                        : "bg-white border border-slate-200 text-slate-800 rounded-bl-md shadow-sm"
                                }`}>
                                    {m.text}
                                </div>
                            </div>
                        ))}
                        {busy && (
                            <div className="flex justify-start">
                                <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-3 py-2 text-sm text-slate-400">
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
                                placeholder="Type your question…"
                                className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2"
                                style={{ outline: "none" }}
                                data-testid="chatbot-input"/>
                            <button onClick={send} disabled={busy || !input.trim()}
                                style={{ backgroundColor: primary }}
                                className="disabled:opacity-50 text-white p-2 rounded-lg"
                                data-testid="chatbot-send">
                                <PaperPlaneTilt size={18} weight="fill"/>
                            </button>
                        </div>
                        <div className="mt-2 text-[10px] text-slate-400 text-center">
                            Powered by AI · This is an automated assistant
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
