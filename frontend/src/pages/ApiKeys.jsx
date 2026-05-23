import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { Key, Plus, Trash, Copy, Check } from "@phosphor-icons/react";

export default function ApiKeys() {
    const [keys, setKeys] = useState([]);
    const [name, setName] = useState("");
    const [planLocked, setPlanLocked] = useState(false);
    const [newKey, setNewKey] = useState(null);
    const [copied, setCopied] = useState(false);

    const load = async () => {
        try {
            const { data } = await api.get("/api-keys");
            setKeys(data);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { load(); }, []);

    const create = async () => {
        if (!name) return;
        try {
            const { data } = await api.post("/api-keys", { name });
            setNewKey(data); setName("");
            await load();
        } catch (e) {
            if (e.response?.status === 402) setPlanLocked(true);
            toast.error(formatApiError(e.response?.data?.detail));
        }
    };

    const revoke = async (id) => {
        if (!confirm("Revoke this key? Any integration using it will stop working immediately.")) return;
        try { await api.delete(`/api-keys/${id}`); toast.success("Key revoked"); await load(); }
        catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const copy = (s) => { navigator.clipboard.writeText(s); setCopied(true); toast.success("Copied"); setTimeout(() => setCopied(false), 1500); };

    if (planLocked) {
        return (
            <div className="max-w-2xl mx-auto py-12 text-center space-y-3">
                <Key size={48} className="mx-auto text-slate-300"/>
                <h2 className="text-2xl font-extrabold text-slate-900">API access requires Pro</h2>
                <p className="text-slate-500">Upgrade to use programmatic API keys for integrations.</p>
                <a href="/app/settings/subscription" className="inline-block mt-3 px-5 py-3 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm">View plans</a>
            </div>
        );
    }

    return (
        <div className="space-y-5 max-w-4xl">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">API keys</h1>
                <p className="text-sm text-slate-500 mt-1">Use these for programmatic access from your own tools and integrations. Authenticate with <code className="bg-slate-100 px-1 rounded">Authorization: Bearer afp_live_…</code></p>
            </header>

            {newKey && (
                <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-4 space-y-2" data-testid="new-key-banner">
                    <div className="font-bold text-amber-900">New key created — copy it now (only shown once)</div>
                    <div className="flex items-center gap-2">
                        <code className="flex-1 truncate bg-white px-3 py-2 rounded border text-sm font-mono">{newKey.key}</code>
                        <button onClick={() => copy(newKey.key)} className="p-2 rounded bg-amber-200 hover:bg-amber-300">
                            {copied ? <Check size={14}/> : <Copy size={14}/>}
                        </button>
                    </div>
                    <button onClick={() => setNewKey(null)} className="text-xs text-amber-700 underline">Dismiss</button>
                </div>
            )}

            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3">
                <div className="flex gap-2">
                    <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Key name (e.g., Zapier integration)"
                        className="flex-1 h-10 px-3 rounded border border-slate-300 text-sm" data-testid="apikey-name"/>
                    <button onClick={create} disabled={!name} className="px-4 py-2 rounded-xl bg-[#1D4ED8] text-white font-bold text-sm disabled:opacity-50 inline-flex items-center gap-2" data-testid="apikey-create-btn">
                        <Plus size={14}/> Create key
                    </button>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
                        <tr>
                            <th className="text-left p-3">Name</th>
                            <th className="text-left p-3">Prefix</th>
                            <th className="text-left p-3">Created</th>
                            <th className="text-left p-3">Last used</th>
                            <th className="text-left p-3">Status</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {keys.map((k) => (
                            <tr key={k.id} className="border-t border-slate-100" data-testid={`apikey-row-${k.id}`}>
                                <td className="p-3 font-bold">{k.name}</td>
                                <td className="p-3 font-mono text-xs">{k.prefix_visible}…</td>
                                <td className="p-3 text-xs">{new Date(k.created_at).toLocaleDateString()}</td>
                                <td className="p-3 text-xs">{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}</td>
                                <td className="p-3"><span className={`text-xs font-bold ${k.active ? "text-green-700" : "text-slate-400"}`}>{k.active ? "Active" : "Revoked"}</span></td>
                                <td className="p-3 text-right">
                                    {k.active && <button onClick={() => revoke(k.id)} className="p-2 rounded hover:bg-rose-50 text-rose-700" data-testid={`apikey-revoke-${k.id}`}><Trash size={14}/></button>}
                                </td>
                            </tr>
                        ))}
                        {!keys.length && (<tr><td colSpan={6} className="p-8 text-center text-slate-500"><Key size={36} className="mx-auto text-slate-300 mb-2"/>No API keys yet.</td></tr>)}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
