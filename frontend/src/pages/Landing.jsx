import { Link } from "react-router-dom";
import Brand from "../components/Brand";
import {
    Wrench, CalendarBlank, ChartLineUp, DeviceMobile,
    ArrowRight, CheckCircle, Lightning, Wind, ShieldCheck,
} from "@phosphor-icons/react";

const HERO_IMG = "https://static.prod-images.emergentagent.com/jobs/69c67260-dedd-4606-94d4-9ad133f7b092/images/f3d45e013f5b8b65923badcaec9a5ae614860b6ec80845d162f8ea44560e52f7.png";
const TECH_IMG = "https://images.unsplash.com/photo-1621905251918-48416bd8575a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwyfHxodmFjJTIwdGVjaG5pY2lhbiUyMHdvcmtpbmd8ZW58MHx8fHwxNzc4OTQ5ODEwfDA&ixlib=rb-4.1.0&q=85";
const PLUMB_IMG = "https://images.unsplash.com/photo-1542013936693-884638332954?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MjJ8MHwxfHNlYXJjaHwxfHxwbHVtYmVyJTIwc2lua3xlbnwwfHx8fDE3Nzg5NDk4MTB8MA&ixlib=rb-4.1.0&q=85";

const trades = [
    { icon: Wind, label: "HVAC" },
    { icon: Wrench, label: "Plumbing" },
    { icon: Lightning, label: "Electrical" },
    { icon: ShieldCheck, label: "Roofing" },
];

export default function Landing() {
    return (
        <div className="min-h-screen bg-white text-slate-900">
            {/* Nav */}
            <header className="sticky top-0 z-30 backdrop-blur-xl bg-white/70 border-b border-slate-200">
                <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-6">
                    <Brand subtitle />
                    <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-700">
                        <a href="#features" className="hover:text-[#1D4ED8]">Features</a>
                        <a href="#industries" className="hover:text-[#1D4ED8]">Industries</a>
                        <Link to="/pricing" className="hover:text-[#1D4ED8]" data-testid="landing-pricing-link">Pricing</Link>
                    </div>
                    <div className="flex items-center gap-3">
                        <Link to="/login" data-testid="nav-signin-link" className="text-sm font-medium px-3 py-1.5 hover:text-[#1D4ED8]">Sign in</Link>
                        <Link
                            to="/register"
                            data-testid="nav-signup-link"
                            className="text-sm font-semibold px-4 py-2 bg-[#DC2626] text-white hover:bg-[#B91C1C] transition-colors"
                        >
                            Start free trial
                        </Link>
                    </div>
                </div>
            </header>

            {/* Hero */}
            <section className="relative overflow-hidden">
                <div className="max-w-7xl mx-auto px-6 pt-16 pb-24 grid lg:grid-cols-12 gap-12 items-end">
                    <div className="lg:col-span-7">
                        <div className="overline mb-6">Field service operating system</div>
                        <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tighter leading-[0.95]">
                            Dispatch faster.<br />
                            <span className="text-[#DC2626]">Close more jobs.</span><br />
                            <span className="text-[#1D4ED8]">Get paid same-day.</span>
                        </h1>
                        <p className="mt-8 text-lg text-slate-600 max-w-xl leading-relaxed">
                            A1 Field Pro is the modern field service platform built for HVAC, plumbing,
                            electrical, roofing and home service crews. Cleaner than Workiz.
                            Simpler than ServiceTitan.
                        </p>
                        <div className="mt-10 flex flex-col sm:flex-row gap-4">
                            <Link
                                to="/register"
                                data-testid="hero-cta-trial-button"
                                className="inline-flex items-center justify-center gap-2 bg-[#1D4ED8] text-white px-7 py-3.5 font-semibold hover:bg-[#1E40AF] transition-colors"
                            >
                                Start your free trial
                                <ArrowRight weight="bold" />
                            </Link>
                            <Link
                                to="/login"
                                data-testid="hero-demo-login-button"
                                className="inline-flex items-center justify-center gap-2 border border-slate-300 px-7 py-3.5 font-semibold hover:bg-slate-50"
                            >
                                Try the demo
                            </Link>
                        </div>
                        <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-600">
                            {["No credit card", "Setup in 5 minutes", "Cancel anytime"].map(t => (
                                <div key={t} className="flex items-center gap-2">
                                    <CheckCircle weight="fill" className="text-[#16A34A]" size={16} />
                                    {t}
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="lg:col-span-5">
                        <div className="relative">
                            <div className="absolute -top-4 -left-4 w-32 h-32 border-2 border-[#DC2626]" />
                            <img src={HERO_IMG} alt="A1 Field Pro command center" className="relative w-full h-auto shadow-xl" />
                            <div className="absolute -bottom-4 -right-4 bg-[#1D4ED8] text-white px-4 py-3">
                                <div className="overline text-white/70">Live</div>
                                <div className="font-display text-2xl font-extrabold">+34% revenue</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="grain absolute inset-0 pointer-events-none" />
            </section>

            {/* Industry strip */}
            <section id="industries" className="border-y border-slate-200 bg-slate-50">
                <div className="max-w-7xl mx-auto px-6 py-8 flex flex-wrap items-center justify-between gap-6">
                    <div className="overline">Built for every trade</div>
                    <div className="flex flex-wrap items-center gap-x-10 gap-y-4">
                        {trades.map(t => (
                            <div key={t.label} className="flex items-center gap-2 text-slate-700 font-medium">
                                <t.icon size={20} weight="duotone" className="text-[#1D4ED8]" />
                                {t.label}
                            </div>
                        ))}
                        <div className="flex items-center gap-2 text-slate-700 font-medium">
                            Garage Doors · Appliance Repair · Roofing
                        </div>
                    </div>
                </div>
            </section>

            {/* Features */}
            <section id="features" className="max-w-7xl mx-auto px-6 py-24">
                <div className="overline mb-4">Why A1 Field Pro</div>
                <h2 className="font-display text-4xl sm:text-5xl font-extrabold tracking-tighter max-w-2xl">
                    Everything your crew needs.
                    <span className="text-slate-400"> Nothing they don't.</span>
                </h2>

                <div className="mt-16 grid md:grid-cols-2 lg:grid-cols-4 gap-px bg-slate-200 border border-slate-200">
                    {[
                        { icon: Wrench, title: "Work Orders", desc: "Create, dispatch, and track jobs from intake to invoice with one click." },
                        { icon: CalendarBlank, title: "Smart Scheduling", desc: "Drag-and-drop dispatch board. See every tech, every job, every minute." },
                        { icon: DeviceMobile, title: "Field App", desc: "Technicians clock in, update status, and collect payment from anywhere." },
                        { icon: ChartLineUp, title: "Real-time KPIs", desc: "Revenue, completion rate, and crew performance — refreshed live." },
                    ].map((f) => (
                        <div key={f.title} className="bg-white p-8 hover:bg-slate-50 transition-colors">
                            <f.icon size={32} weight="duotone" className="text-[#1D4ED8]" />
                            <h3 className="font-heading text-xl font-semibold mt-6">{f.title}</h3>
                            <p className="mt-3 text-sm text-slate-600 leading-relaxed">{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Showcase */}
            <section className="bg-slate-900 text-white">
                <div className="max-w-7xl mx-auto px-6 py-24 grid lg:grid-cols-12 gap-12 items-center">
                    <div className="lg:col-span-5">
                        <div className="overline text-slate-400">For the field</div>
                        <h2 className="font-display text-4xl sm:text-5xl font-extrabold tracking-tighter mt-4">
                            A mobile app your techs will <span className="text-[#DC2626]">actually open</span>.
                        </h2>
                        <p className="mt-6 text-slate-300 leading-relaxed">
                            Today's jobs, optimized routes, customer history, photo capture,
                            signature, and Stripe checkout — all from a phone.
                        </p>
                        <ul className="mt-8 space-y-3 text-slate-200">
                            {["My day at a glance", "One-tap status updates", "Same-day card payments", "Works offline"].map((t) => (
                                <li key={t} className="flex items-center gap-3">
                                    <CheckCircle weight="fill" className="text-[#DC2626]" size={18} />
                                    {t}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="lg:col-span-7 grid grid-cols-2 gap-6">
                        <img src={TECH_IMG} alt="Technician" className="w-full h-80 object-cover" />
                        <img src={PLUMB_IMG} alt="Plumbing service" className="w-full h-80 object-cover mt-12" />
                    </div>
                </div>
            </section>

            {/* CTA */}
            <section id="pricing" className="max-w-7xl mx-auto px-6 py-24 text-center">
                <div className="overline mb-4">Ready when you are</div>
                <h2 className="font-display text-4xl sm:text-6xl font-extrabold tracking-tighter">
                    Run your field business like a <span className="text-[#1D4ED8]">pro</span>.
                </h2>
                <Link
                    to="/register"
                    data-testid="footer-cta-button"
                    className="mt-10 inline-flex items-center gap-2 bg-[#DC2626] text-white px-8 py-4 font-semibold hover:bg-[#B91C1C] transition-colors"
                >
                    Start free for 14 days <ArrowRight weight="bold" />
                </Link>
            </section>

            <footer className="border-t border-slate-200">
                <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-slate-500">
                    <Brand />
                    <div>© 2026 A1 HVAC N DE-GO. All rights reserved.</div>
                </div>
            </footer>
        </div>
    );
}
