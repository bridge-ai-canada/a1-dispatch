import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { CheckCircle, Star, Lightning, Crown, Sparkle } from "@phosphor-icons/react";

const ICONS = { starter: Sparkle, lite: Lightning, pro: Star, enterprise: Crown };

export default function Subscription() {
    const [plans, setPlans] = useState([]);
    const [sub, setSub] = useState(null);
    const [busy, setBusy] = useState("");

    const load = async () => {
        try {
            const [{ data: p }, { data: s }] = await Promise.all([
                api.get("/subscription/plans"),
                api.get("/subscription"),
            ]);
            setPlans(p); setSub(s);
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };
    useEffect(() => { load(); }, []);

    const checkout = async (planKey) => {
        setBusy(planKey);
        try {
            const { data } = await api.post("/subscription/checkout", {
                plan: planKey,
                origin_url: window.location.origin,
            });
            if (data.checkout_url) {
                window.location.href = data.checkout_url;
            } else {
                toast.success(data.message || "Plan changed");
                await load();
            }
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setBusy(""); }
    };

    return (
        <div className="space-y-6 max-w-6xl">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Subscription</h1>
                <p className="text-sm text-slate-500 mt-1">Choose the plan that fits your team. Upgrade or downgrade anytime.</p>
            </header>

            {sub && (
                <div className="bg-gradient-to-r from-slate-900 to-slate-700 text-white rounded-2xl p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" data-testid="current-sub-card">
                    <div>
                        <div className="text-xs uppercase tracking-wider opacity-70">Current plan</div>
                        <div className="text-2xl font-extrabold">{sub.plan.name}</div>
                        <div className="text-xs opacity-70 mt-1">
                            Status: <span className="font-semibold">{sub.status}</span> · Seats: {sub.seats_used} / {sub.seats_limit === 0 ? "∞" : sub.seats_limit}
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-3xl font-extrabold">${sub.plan.price_usd}</div>
                        <div className="text-xs opacity-70">/ {sub.plan.interval}</div>
                    </div>
                </div>
            )}

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                {plans.map((p) => {
                    const Icon = ICONS[p.key] || Sparkle;
                    const isCurrent = sub?.plan?.key === p.key;
                    return (
                        <div key={p.key} className={`rounded-2xl border-2 p-5 space-y-4 ${p.featured ? "border-[#1D4ED8] shadow-lg" : "border-slate-200"} ${isCurrent ? "bg-slate-50" : "bg-white"}`} data-testid={`plan-${p.key}`}>
                            {p.featured && <div className="inline-block text-[10px] font-bold uppercase tracking-wider bg-[#1D4ED8] text-white px-2 py-0.5 rounded-full">Most popular</div>}
                            <div className="flex items-center gap-2">
                                <Icon size={24} weight={p.featured ? "fill" : "regular"} className={p.featured ? "text-[#1D4ED8]" : "text-slate-700"}/>
                                <div className="font-extrabold text-xl">{p.name}</div>
                            </div>
                            <div>
                                <div className="text-4xl font-extrabold">${p.price_usd}</div>
                                <div className="text-xs text-slate-500">/ {p.interval}</div>
                            </div>
                            <div className="text-xs text-slate-600">{p.tagline}</div>
                            <ul className="space-y-1 text-xs">
                                <li className="flex items-center gap-1"><CheckCircle size={14} className="text-green-600"/> {p.seats === 0 ? "Unlimited seats" : `${p.seats} seats`}</li>
                                <li className={`flex items-center gap-1 ${p.features.ai_assist ? "" : "text-slate-400 line-through"}`}><CheckCircle size={14} className={p.features.ai_assist ? "text-green-600" : "text-slate-300"}/> AI assistant</li>
                                <li className={`flex items-center gap-1 ${p.features.branches ? "" : "text-slate-400 line-through"}`}><CheckCircle size={14} className={p.features.branches ? "text-green-600" : "text-slate-300"}/> Multi-branch</li>
                                <li className={`flex items-center gap-1 ${p.features.api_access ? "" : "text-slate-400 line-through"}`}><CheckCircle size={14} className={p.features.api_access ? "text-green-600" : "text-slate-300"}/> API access</li>
                                <li className={`flex items-center gap-1 ${p.features.custom_domain ? "" : "text-slate-400 line-through"}`}><CheckCircle size={14} className={p.features.custom_domain ? "text-green-600" : "text-slate-300"}/> Custom domain</li>
                                <li className={`flex items-center gap-1 ${p.features.franchise ? "" : "text-slate-400 line-through"}`}><CheckCircle size={14} className={p.features.franchise ? "text-green-600" : "text-slate-300"}/> Franchise</li>
                            </ul>
                            <button
                                disabled={isCurrent || busy === p.key}
                                onClick={() => checkout(p.key)}
                                className={`w-full px-4 py-3 rounded-xl font-bold text-sm transition ${
                                    isCurrent ? "bg-slate-200 text-slate-500 cursor-default" :
                                    p.featured ? "bg-[#1D4ED8] text-white hover:bg-blue-700" :
                                    "bg-slate-900 text-white hover:bg-black"
                                }`}
                                data-testid={`plan-cta-${p.key}`}>
                                {isCurrent ? "Current plan" : busy === p.key ? "Loading…" : `Switch to ${p.name}`}
                            </button>
                        </div>
                    );
                })}
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 text-xs text-slate-600">
                Billing handled by Stripe. Custom domain & franchise features require Enterprise. Per-tenant API keys available on Pro & Enterprise — manage them on the <a href="/app/settings/api-keys" className="underline font-semibold">API keys</a> page.
            </div>
        </div>
    );
}
