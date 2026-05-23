import { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import axios from "axios";
import { API_BASE } from "../lib/api";
import { Phone, EnvelopeSimple, MapTrifold, ArrowRight, CheckCircle, Wrench, Lightning, Shield, Calendar, Star } from "@phosphor-icons/react";

/* Public, white-labeled landing page rendered for each tenant.
   Accessed via /site/:companyId  OR  /site?domain=<custom-domain>.
   Pulls from GET /api/public/branding (unauthenticated) and uses
   the booking widget URL the tenant already publishes. */
export default function TenantLanding() {
    const params = useParams();
    const [search] = useSearchParams();
    const [brand, setBrand] = useState(null);
    const [err, setErr] = useState("");

    const companyId = params.companyId;
    const domain = search.get("domain");

    useEffect(() => {
        const q = companyId ? { company_id: companyId } : domain ? { domain } : null;
        if (!q) { setErr("Missing tenant identifier"); return; }
        axios.get(`${API_BASE}/public/branding`, { params: q })
            .then(({ data }) => setBrand(data))
            .catch((e) => setErr(e.response?.data?.detail || "Tenant not found"));
    }, [companyId, domain]);

    useEffect(() => {
        if (brand?.app_name) document.title = brand.app_name;
        // Inject favicon if provided
        if (brand?.favicon_path) {
            const link = document.querySelector("link[rel*='icon']") || document.createElement("link");
            link.type = "image/png";
            link.rel = "shortcut icon";
            link.href = `${API_BASE.replace("/api","")}/api/files/${encodeURIComponent(brand.favicon_path)}`;
            document.head.appendChild(link);
        }
    }, [brand]);

    if (err) {
        return (
            <div className="min-h-screen grid place-items-center bg-slate-50 text-center p-6">
                <div className="max-w-md space-y-3">
                    <div className="text-6xl">🛠️</div>
                    <h1 className="text-2xl font-extrabold">{err}</h1>
                    <p className="text-slate-500">This page is unavailable. Check the link or contact the company.</p>
                </div>
            </div>
        );
    }
    if (!brand) {
        return <div className="min-h-screen grid place-items-center text-slate-400 text-sm">Loading…</div>;
    }

    const primary = brand.primary_color || "#1D4ED8";
    const accent = brand.accent_color || "#DC2626";
    const secondary = brand.secondary_color || "#0F172A";
    const logoUrl = brand.logo_path ? `${API_BASE.replace("/api","")}/api/files/${encodeURIComponent(brand.logo_path)}` : "";
    const bookingUrl = `/book/${brand.company_id}`;

    return (
        <div className="min-h-screen bg-white text-slate-900" style={{ "--brand-primary": primary, "--brand-accent": accent, "--brand-secondary": secondary }}>
            {/* Nav */}
            <header className="sticky top-0 z-30 backdrop-blur-xl bg-white/80 border-b border-slate-200">
                <div className="max-w-7xl mx-auto flex items-center justify-between h-16 px-6">
                    <div className="flex items-center gap-3" data-testid="tenant-brand">
                        {logoUrl ? <img src={logoUrl} alt={brand.app_name} className="h-9 max-w-32 object-contain"/> :
                            <div className="font-extrabold text-xl tracking-tight" style={{ color: primary }}>{brand.app_name}</div>}
                    </div>
                    <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-700">
                        <a href="#services" className="hover:opacity-70">Services</a>
                        <a href="#how" className="hover:opacity-70">How it works</a>
                        <a href="#contact" className="hover:opacity-70">Contact</a>
                    </nav>
                    <div className="flex items-center gap-3">
                        {brand.support_phone && <a href={`tel:${brand.support_phone}`} className="hidden sm:inline-flex items-center gap-1 text-sm font-medium text-slate-700"><Phone size={14}/>{brand.support_phone}</a>}
                        <Link to={bookingUrl} className="text-sm font-semibold px-4 py-2 text-white" style={{ background: accent }} data-testid="tenant-cta-nav">
                            Book service
                        </Link>
                    </div>
                </div>
            </header>

            {/* Hero */}
            <section className="relative overflow-hidden" style={{ background: `linear-gradient(135deg, ${primary} 0%, ${secondary} 100%)` }}>
                <div className="max-w-7xl mx-auto px-6 py-20 lg:py-28 text-white relative z-10">
                    <div className="max-w-2xl space-y-6">
                        <div className="inline-block px-3 py-1 rounded-full bg-white/10 backdrop-blur text-xs font-bold uppercase tracking-wider">Trusted local service</div>
                        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tighter leading-[0.95]">
                            {brand.tagline || `${brand.app_name} — service that just works.`}
                        </h1>
                        <p className="text-lg sm:text-xl opacity-90 max-w-xl">
                            Same-day appointments. Upfront pricing. Friendly techs. Book online in 60 seconds.
                        </p>
                        <div className="flex flex-wrap gap-3 pt-3">
                            <Link to={bookingUrl} data-testid="tenant-cta-primary"
                                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm shadow-lg" style={{ background: accent, color: "white" }}>
                                Book an appointment <ArrowRight size={14}/>
                            </Link>
                            {brand.support_phone && (
                                <a href={`tel:${brand.support_phone}`} className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white/10 backdrop-blur font-bold text-sm border border-white/20 hover:bg-white/20" data-testid="tenant-cta-call">
                                    <Phone size={14}/> Call {brand.support_phone}
                                </a>
                            )}
                        </div>
                        <div className="flex items-center gap-4 pt-4 text-xs opacity-80">
                            <span className="flex items-center gap-1"><CheckCircle size={14}/> Same-day appts</span>
                            <span className="flex items-center gap-1"><Shield size={14}/> Licensed & insured</span>
                            <span className="flex items-center gap-1"><Star size={14}/> 5-star rated</span>
                        </div>
                    </div>
                </div>
                <div className="absolute right-0 top-0 w-1/3 h-full opacity-10" style={{
                    backgroundImage: "radial-gradient(circle, white 1px, transparent 1px)",
                    backgroundSize: "32px 32px",
                }}/>
            </section>

            {/* Services */}
            <section id="services" className="max-w-7xl mx-auto px-6 py-20">
                <div className="text-center mb-12">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">What we do</div>
                    <h2 className="text-4xl font-extrabold tracking-tighter">Service you can count on.</h2>
                </div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                        { icon: Wrench, label: "Repair & maintenance" },
                        { icon: Calendar, label: "Scheduled tune-ups" },
                        { icon: Lightning, label: "Emergency service" },
                        { icon: Shield, label: "Annual plans" },
                    ].map(({ icon: Icon, label }) => (
                        <div key={label} className="rounded-2xl border-2 border-slate-100 p-5 hover:border-slate-300 transition" data-testid={`tenant-service-${label.toLowerCase().replace(/\s+/g, '-')}`}>
                            <Icon size={32} weight="duotone" style={{ color: primary }}/>
                            <div className="mt-3 font-bold">{label}</div>
                            <div className="text-xs text-slate-500 mt-1">Fast, professional, guaranteed.</div>
                        </div>
                    ))}
                </div>
            </section>

            {/* How it works */}
            <section id="how" className="bg-slate-50 py-20">
                <div className="max-w-5xl mx-auto px-6">
                    <div className="text-center mb-12">
                        <div className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">How it works</div>
                        <h2 className="text-4xl font-extrabold tracking-tighter">Book in 60 seconds.</h2>
                    </div>
                    <div className="grid md:grid-cols-3 gap-5">
                        {[
                            { n: 1, title: "Book online", desc: "Pick a service and a time that works for you." },
                            { n: 2, title: "We confirm", desc: "Get instant SMS + email confirmation with tech details." },
                            { n: 3, title: "Job done", desc: "Friendly tech arrives on time. Pay securely after the work." },
                        ].map((s) => (
                            <div key={s.n} className="bg-white rounded-2xl border border-slate-200 p-6 relative">
                                <div className="absolute -top-4 left-6 w-10 h-10 rounded-full grid place-items-center text-white font-extrabold" style={{ background: accent }}>{s.n}</div>
                                <div className="mt-3 font-bold text-lg">{s.title}</div>
                                <div className="text-sm text-slate-600 mt-2">{s.desc}</div>
                            </div>
                        ))}
                    </div>
                    <div className="text-center mt-10">
                        <Link to={bookingUrl} className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm text-white shadow-md" style={{ background: primary }} data-testid="tenant-cta-how">
                            Start booking <ArrowRight size={14}/>
                        </Link>
                    </div>
                </div>
            </section>

            {/* Contact */}
            <section id="contact" className="max-w-5xl mx-auto px-6 py-20">
                <div className="grid md:grid-cols-2 gap-8">
                    <div>
                        <div className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">Get in touch</div>
                        <h2 className="text-4xl font-extrabold tracking-tighter mb-5">We're here when you need us.</h2>
                        <div className="space-y-3 text-sm">
                            {brand.support_phone && (
                                <a href={`tel:${brand.support_phone}`} className="flex items-center gap-3 hover:opacity-70" data-testid="tenant-contact-phone">
                                    <div className="w-10 h-10 rounded-full grid place-items-center text-white" style={{ background: primary }}><Phone size={16}/></div>
                                    <div><div className="text-xs uppercase tracking-wider text-slate-500">Phone</div><div className="font-bold">{brand.support_phone}</div></div>
                                </a>
                            )}
                            {brand.support_email && (
                                <a href={`mailto:${brand.support_email}`} className="flex items-center gap-3 hover:opacity-70" data-testid="tenant-contact-email">
                                    <div className="w-10 h-10 rounded-full grid place-items-center text-white" style={{ background: primary }}><EnvelopeSimple size={16}/></div>
                                    <div><div className="text-xs uppercase tracking-wider text-slate-500">Email</div><div className="font-bold">{brand.support_email}</div></div>
                                </a>
                            )}
                        </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 p-6 bg-gradient-to-br from-slate-50 to-white">
                        <div className="text-sm font-bold mb-3">Or book online now</div>
                        <Link to={bookingUrl} className="block text-center w-full px-4 py-3 rounded-xl font-bold text-sm text-white" style={{ background: accent }} data-testid="tenant-cta-contact">
                            Book service →
                        </Link>
                        <div className="mt-3 text-xs text-slate-500 text-center">Takes 60 seconds. No account required.</div>
                    </div>
                </div>
            </section>

            <footer className="border-t border-slate-200 py-8 text-center text-xs text-slate-500" data-testid="tenant-footer">
                © {new Date().getFullYear()} {brand.company_name}. All rights reserved.
                <div className="mt-1 opacity-60">Powered by A1 Field Pro</div>
            </footer>
        </div>
    );
}
