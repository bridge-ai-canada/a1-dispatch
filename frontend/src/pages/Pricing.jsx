import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { API_BASE } from "../lib/api";
import Brand from "../components/Brand";
import { CheckCircle, X, Star, Lightning, Crown, Sparkle, ArrowRight, Check } from "@phosphor-icons/react";

const ICONS = { starter: Sparkle, lite: Lightning, pro: Star, enterprise: Crown };
const FEATURE_ROWS = [
    { key: "seats",          label: "Team seats",     render: (p) => p.seats === 0 ? "Unlimited" : p.seats },
    { key: "white_label",    label: "White-label branding", flag: true },
    { key: "sms_reminders",  label: "SMS reminders (Twilio)", flag: true },
    { key: "ai_assist",      label: "AI assistant + dispatcher", flag: true },
    { key: "branches",       label: "Multi-branch operations", flag: true },
    { key: "api_access",     label: "API access + per-tenant keys", flag: true },
    { key: "custom_domain",  label: "Custom domain (CNAME)", flag: true },
    { key: "franchise",      label: "Franchise rollup metrics", flag: true },
];

const FAQ = [
    { q: "Can I switch plans later?", a: "Yes — upgrade or downgrade anytime. Billing prorates automatically." },
    { q: "Is there a free trial?", a: "Every plan ships with a 14-day trial. No card required to start." },
    { q: "What payment methods do you accept?", a: "All major credit cards via Stripe (Visa, Mastercard, Amex, Discover). Annual invoicing available for Enterprise." },
    { q: "What does white-label include?", a: "Your logo, colors, app name, custom email/SMS templates, support email/phone, invoice footer — and on Enterprise, a CNAME custom domain." },
];

export default function Pricing() {
    const [plans, setPlans] = useState([]);
    const [billing, setBilling] = useState("month"); // monthly only for now; annual placeholder

    useEffect(() => {
        axios.get(`${API_BASE}/subscription/plans`).then(({ data }) => setPlans(data)).catch(() => {});
    }, []);

    return (
        <div className="min-h-screen bg-white text-slate-900">
            {/* Nav */}
            <header className="sticky top-0 z-30 backdrop-blur-xl bg-white/80 border-b border-slate-200">
                <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-6">
                    <Link to="/" data-testid="pricing-home"><Brand subtitle /></Link>
                    <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-700">
                        <Link to="/" className="hover:text-[#1D4ED8]">Home</Link>
                        <a href="#compare" className="hover:text-[#1D4ED8]">Compare</a>
                        <a href="#faq" className="hover:text-[#1D4ED8]">FAQ</a>
                    </nav>
                    <div className="flex items-center gap-3">
                        <Link to="/login" data-testid="pricing-signin" className="text-sm font-medium px-3 py-1.5 hover:text-[#1D4ED8]">Sign in</Link>
                        <Link to="/register" data-testid="pricing-cta-nav" className="text-sm font-semibold px-4 py-2 bg-[#DC2626] text-white hover:bg-[#B91C1C]">Start free trial</Link>
                    </div>
                </div>
            </header>

            {/* Hero */}
            <section className="max-w-5xl mx-auto px-6 pt-16 pb-10 text-center">
                <div className="overline mb-4 inline-block text-xs uppercase tracking-[0.2em] text-slate-500">Pricing</div>
                <h1 className="font-display text-5xl sm:text-6xl font-extrabold tracking-tighter leading-none">
                    Pricing built for<br/>
                    <span className="text-[#1D4ED8]">growing field teams.</span>
                </h1>
                <p className="mt-5 text-lg text-slate-600 max-w-2xl mx-auto">
                    Pick a plan, white-label everything, scale to thousands of techs. 14-day free trial on every tier — no card required.
                </p>
                {/* Billing toggle (annual placeholder for future) */}
                <div className="mt-7 inline-flex rounded-full border border-slate-200 p-1 bg-slate-50">
                    <button onClick={() => setBilling("month")} className={`text-xs font-bold px-4 py-1.5 rounded-full ${billing === "month" ? "bg-white shadow text-slate-900" : "text-slate-500"}`} data-testid="billing-monthly">Monthly</button>
                    <button onClick={() => setBilling("annual")} className={`text-xs font-bold px-4 py-1.5 rounded-full ${billing === "annual" ? "bg-white shadow text-slate-900" : "text-slate-500"}`} data-testid="billing-annual">Annual <span className="ml-1 text-green-600">save 15%</span></button>
                </div>
            </section>

            {/* Plan cards */}
            <section className="max-w-7xl mx-auto px-6 pb-16">
                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5" data-testid="pricing-cards">
                    {plans.map((p) => {
                        const Icon = ICONS[p.key] || Sparkle;
                        const monthly = p.price_usd;
                        const display = billing === "annual" ? Math.round(monthly * 0.85) : monthly;
                        return (
                            <div key={p.key} className={`rounded-2xl border-2 p-6 space-y-5 transition hover:shadow-xl ${p.featured ? "border-[#1D4ED8] shadow-lg relative" : "border-slate-200"}`} data-testid={`pricing-card-${p.key}`}>
                                {p.featured && <div className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] font-bold uppercase tracking-wider bg-[#1D4ED8] text-white px-2 py-1 rounded-full">Most popular</div>}
                                <div className="flex items-center gap-2">
                                    <Icon size={24} weight={p.featured ? "fill" : "regular"} className={p.featured ? "text-[#1D4ED8]" : "text-slate-700"}/>
                                    <div className="font-extrabold text-xl">{p.name}</div>
                                </div>
                                <div>
                                    <div className="flex items-baseline gap-1">
                                        <div className="text-5xl font-extrabold tracking-tighter">${display}</div>
                                        <div className="text-sm text-slate-500">/ mo</div>
                                    </div>
                                    {billing === "annual" && <div className="text-[10px] text-green-700 font-bold mt-1">${display * 12}/yr billed annually</div>}
                                </div>
                                <div className="text-sm text-slate-600 min-h-[2.5rem]">{p.tagline}</div>
                                <ul className="space-y-2 text-sm">
                                    <li className="flex items-center gap-2"><Check size={14} className="text-green-600 flex-shrink-0"/> {p.seats === 0 ? "Unlimited seats" : `${p.seats} team seats`}</li>
                                    {[
                                        ["ai_assist", "AI assistant"],
                                        ["branches", "Multi-branch"],
                                        ["api_access", "API access"],
                                        ["custom_domain", "Custom domain"],
                                        ["franchise", "Franchise rollups"],
                                    ].map(([k, label]) => (
                                        <li key={k} className={`flex items-center gap-2 ${p.features[k] ? "" : "text-slate-300"}`}>
                                            {p.features[k] ? <Check size={14} className="text-green-600 flex-shrink-0"/> : <X size={14} className="flex-shrink-0"/>}
                                            <span className={p.features[k] ? "" : "line-through"}>{label}</span>
                                        </li>
                                    ))}
                                </ul>
                                <Link to="/register" data-testid={`pricing-cta-${p.key}`}
                                    className={`block w-full text-center px-4 py-3 rounded-xl font-bold text-sm transition ${
                                        p.featured ? "bg-[#1D4ED8] text-white hover:bg-blue-700" : "bg-slate-900 text-white hover:bg-black"
                                    }`}>
                                    Start free trial <ArrowRight size={14} className="inline ml-1"/>
                                </Link>
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* Compare table */}
            <section id="compare" className="max-w-6xl mx-auto px-6 py-16">
                <h2 className="text-3xl font-extrabold tracking-tight text-center mb-10">Compare plans</h2>
                <div className="overflow-x-auto rounded-2xl border border-slate-200">
                    <table className="w-full text-sm" data-testid="compare-table">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="text-left p-4 font-bold">Feature</th>
                                {plans.map((p) => (
                                    <th key={p.key} className={`p-4 font-bold text-center ${p.featured ? "text-[#1D4ED8]" : ""}`}>{p.name}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {FEATURE_ROWS.map((row, idx) => (
                                <tr key={row.key} className={idx % 2 ? "bg-slate-50" : ""}>
                                    <td className="p-4 font-medium">{row.label}</td>
                                    {plans.map((p) => (
                                        <td key={p.key} className="p-4 text-center">
                                            {row.flag ? (
                                                p.features[row.key]
                                                    ? <CheckCircle size={18} weight="fill" className="text-green-600 inline" />
                                                    : <X size={16} className="text-slate-300 inline"/>
                                            ) : (
                                                <span className="font-bold">{row.render(p)}</span>
                                            )}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>

            {/* FAQ */}
            <section id="faq" className="max-w-3xl mx-auto px-6 py-16">
                <h2 className="text-3xl font-extrabold tracking-tight text-center mb-8">Frequently asked</h2>
                <div className="space-y-3" data-testid="pricing-faq">
                    {FAQ.map((f, i) => (
                        <details key={i} className="bg-white border border-slate-200 rounded-xl p-4 group">
                            <summary className="font-bold cursor-pointer flex items-center justify-between">
                                {f.q}
                                <ArrowRight size={14} className="group-open:rotate-90 transition"/>
                            </summary>
                            <p className="mt-3 text-sm text-slate-600">{f.a}</p>
                        </details>
                    ))}
                </div>
            </section>

            {/* CTA */}
            <section className="bg-slate-900 text-white py-16 text-center">
                <div className="max-w-3xl mx-auto px-6 space-y-5">
                    <h2 className="text-4xl font-extrabold tracking-tighter">Ready when you are.</h2>
                    <p className="text-slate-300">Spin up a fully-branded field service platform in under five minutes.</p>
                    <Link to="/register" data-testid="pricing-cta-bottom" className="inline-block px-8 py-4 bg-[#DC2626] hover:bg-[#B91C1C] font-bold text-sm">Start 14-day free trial</Link>
                </div>
            </section>

            <footer className="border-t border-slate-200 py-8 text-center text-xs text-slate-500">
                <Link to="/" className="hover:text-[#1D4ED8]">← back to home</Link>
            </footer>
        </div>
    );
}
