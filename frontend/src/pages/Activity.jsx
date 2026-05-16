import { useEffect, useState } from "react";
import api from "../lib/api";

const ACTION_COLORS = {
    "auth.login": "bg-blue-50 text-[#1D4ED8] border-[#1D4ED8]/30",
    "auth.logout": "bg-slate-50 text-slate-700 border-slate-300",
    "user.invited": "bg-emerald-50 text-emerald-700 border-emerald-400",
    "user.updated": "bg-amber-50 text-amber-700 border-amber-400",
    "mfa.enabled": "bg-emerald-50 text-emerald-700 border-emerald-400",
    "mfa.disabled": "bg-red-50 text-[#DC2626] border-[#DC2626]/40",
    "company.created": "bg-purple-50 text-purple-700 border-purple-400",
};

export default function Activity() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        api.get("/activity?limit=100").then((r) => setItems(r.data)).finally(() => setLoading(false));
    }, []);

    return (
        <div data-testid="activity-page" className="space-y-6">
            <div>
                <div className="overline">Administration</div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Activity log</h1>
                <p className="text-sm text-slate-500 mt-2">Audit trail of key events across your workspace.</p>
            </div>

            <div className="border border-slate-200">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr className="text-left">
                            <th className="px-4 py-3 font-semibold">When</th>
                            <th className="px-4 py-3 font-semibold">Actor</th>
                            <th className="px-4 py-3 font-semibold">Action</th>
                            <th className="px-4 py-3 font-semibold">Target</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {loading && (<tr><td colSpan={4} className="p-8 text-center text-slate-500">Loading...</td></tr>)}
                        {!loading && items.length === 0 && (
                            <tr><td colSpan={4} className="p-12 text-center text-slate-500">No activity yet.</td></tr>
                        )}
                        {items.map((a) => (
                            <tr key={a.id} data-testid={`activity-row-${a.id}`}>
                                <td className="px-4 py-3 text-slate-500 font-mono text-xs whitespace-nowrap">
                                    {new Date(a.created_at).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}
                                </td>
                                <td className="px-4 py-3">
                                    <div className="font-medium">{a.actor_name || "—"}</div>
                                    <div className="text-xs text-slate-500">{a.actor_role}</div>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`text-xs px-2 py-1 border font-mono ${ACTION_COLORS[a.action] || "bg-slate-50 text-slate-700 border-slate-300"}`}>{a.action}</span>
                                </td>
                                <td className="px-4 py-3 text-slate-500 text-xs">
                                    {a.target_type && <span>{a.target_type} · {(a.target_id || "").slice(0,8)}</span>}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
