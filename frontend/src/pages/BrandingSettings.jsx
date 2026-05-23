import { useEffect, useRef, useState } from "react";
import api, { API_BASE, formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { UploadSimple, Copy, Check, Globe, PaintBrush, EnvelopeSimple, Phone, Image as ImageIcon } from "@phosphor-icons/react";

const PRESETS = [
    { name: "Signal Blue",    primary: "#1D4ED8", accent: "#DC2626", secondary: "#0F172A" },
    { name: "Forest",         primary: "#15803D", accent: "#F97316", secondary: "#052E16" },
    { name: "Royal",          primary: "#7C3AED", accent: "#F59E0B", secondary: "#1E1B4B" },
    { name: "Slate",          primary: "#0F172A", accent: "#EAB308", secondary: "#000000" },
    { name: "Ocean",          primary: "#0E7490", accent: "#DC2626", secondary: "#083344" },
    { name: "Sunset",         primary: "#BE185D", accent: "#F59E0B", secondary: "#500724" },
];

function ColorField({ label, value, onChange, testid }) {
    return (
        <label className="block">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">{label}</span>
            <div className="mt-1 flex items-center gap-2">
                <input type="color" value={value} onChange={(e) => onChange(e.target.value)}
                    className="h-10 w-12 rounded border border-slate-300 cursor-pointer"
                    data-testid={`${testid}-picker`} />
                <input type="text" value={value} onChange={(e) => onChange(e.target.value)}
                    className="flex-1 h-10 px-3 rounded border border-slate-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30"
                    data-testid={`${testid}-input`} />
            </div>
        </label>
    );
}

export default function BrandingSettings() {
    const { company, refresh } = useAuth();
    const fileLogoRef = useRef(null);
    const fileFaviconRef = useRef(null);
    const [saving, setSaving] = useState(false);
    const [copied, setCopied] = useState("");
    const [form, setForm] = useState({
        primary_color: "#1D4ED8", accent_color: "#DC2626", secondary_color: "#0F172A",
        app_name: "", tagline: "", custom_domain: "",
        support_email: "", support_phone: "", invoice_footer: "", email_from_name: "",
        logo_path: "", favicon_path: "",
    });

    useEffect(() => {
        (async () => {
            const { data } = await api.get("/branding");
            const b = data.branding || {};
            setForm((f) => ({
                ...f,
                primary_color: b.primary_color || "#1D4ED8",
                accent_color: b.accent_color || "#DC2626",
                secondary_color: b.secondary_color || "#0F172A",
                app_name: b.app_name || data.company_name || "",
                tagline: b.tagline || "",
                custom_domain: b.custom_domain || "",
                support_email: b.support_email || "",
                support_phone: b.support_phone || "",
                invoice_footer: b.invoice_footer || "",
                email_from_name: b.email_from_name || "",
                logo_path: b.logo_path || "", favicon_path: b.favicon_path || "",
            }));
        })().catch(() => {});
    }, [company?.id]);

    const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
    const applyPreset = (p) => setForm((f) => ({ ...f, primary_color: p.primary, accent_color: p.accent, secondary_color: p.secondary }));

    const upload = async (file, kind) => {
        if (!file) return;
        const fd = new FormData(); fd.append("file", file);
        try {
            const { data } = await api.post(`/branding/upload-${kind}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
            set(kind === "logo" ? "logo_path" : "favicon_path", data.path);
            toast.success(`${kind === "logo" ? "Logo" : "Favicon"} uploaded`);
            await refresh?.();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    };

    const save = async () => {
        setSaving(true);
        try {
            const payload = { ...form };
            // Don't send empty strings for color fields (they'd fail validation)
            ["primary_color", "accent_color", "secondary_color"].forEach((k) => {
                if (payload[k] && !/^#[0-9A-Fa-f]{6}$/.test(payload[k])) delete payload[k];
            });
            // Don't send paths from the form — only updated via upload endpoints.
            delete payload.logo_path; delete payload.favicon_path;
            await api.patch("/branding", payload);
            toast.success("Branding saved");
            await refresh?.();
        } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
        finally { setSaving(false); }
    };

    const copy = (txt, label) => {
        try {
            navigator.clipboard.writeText(txt).catch(() => {
                // Fallback for sandboxed iframes / older browsers
                const ta = document.createElement("textarea"); ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
                document.body.appendChild(ta); ta.select();
                try { document.execCommand("copy"); } catch (_) {}
                document.body.removeChild(ta);
            });
        } catch (_) {}
        setCopied(label); toast.success(`${label} copied`); setTimeout(() => setCopied(""), 1500);
    };

    const logoUrl = form.logo_path ? `${API_BASE.replace("/api","")}/api/public/branding/asset/${company?.id || ''}/logo?v=${encodeURIComponent(form.logo_path)}` : "";
    const faviconUrl = form.favicon_path ? `${API_BASE.replace("/api","")}/api/public/branding/asset/${company?.id || ''}/favicon?v=${encodeURIComponent(form.favicon_path)}` : "";

    return (
        <div className="space-y-6 max-w-6xl">
            <header>
                <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Branding & White-Label</h1>
                <p className="text-sm text-slate-500 mt-1">Customize your app's name, colors, logo, and contact info. Changes apply to invoices, emails, customer portals, and the booking widget.</p>
            </header>

            <div className="grid lg:grid-cols-3 gap-6">
                {/* Form */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Identity */}
                    <section className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                        <h2 className="font-bold text-slate-900 flex items-center gap-2"><PaintBrush size={18}/> Identity</h2>
                        <label className="block">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Product / app name</span>
                            <input type="text" value={form.app_name} onChange={(e) => set("app_name", e.target.value)}
                                placeholder="e.g. Acme Field Pro"
                                className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30"
                                data-testid="branding-appname-input" />
                        </label>
                        <label className="block">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Tagline</span>
                            <input type="text" value={form.tagline} onChange={(e) => set("tagline", e.target.value)}
                                placeholder="A short marketing line"
                                className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30"
                                data-testid="branding-tagline-input" />
                        </label>
                    </section>

                    {/* Colors */}
                    <section className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                        <h2 className="font-bold text-slate-900 flex items-center gap-2"><PaintBrush size={18}/> Colors</h2>
                        <div className="grid sm:grid-cols-3 gap-3">
                            <ColorField label="Primary" value={form.primary_color} onChange={(v) => set("primary_color", v)} testid="branding-primary" />
                            <ColorField label="Accent" value={form.accent_color} onChange={(v) => set("accent_color", v)} testid="branding-accent" />
                            <ColorField label="Secondary" value={form.secondary_color} onChange={(v) => set("secondary_color", v)} testid="branding-secondary" />
                        </div>
                        <div className="pt-2">
                            <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Presets</div>
                            <div className="flex flex-wrap gap-2">
                                {PRESETS.map((p) => (
                                    <button key={p.name} onClick={() => applyPreset(p)}
                                        className="px-3 py-2 rounded-lg border border-slate-200 hover:border-slate-400 text-xs font-semibold flex items-center gap-2"
                                        data-testid={`branding-preset-${p.name.replace(/\s+/g, '-').toLowerCase()}`}>
                                        <span className="flex gap-1">
                                            <span className="w-3 h-3 rounded-sm" style={{ background: p.primary }} />
                                            <span className="w-3 h-3 rounded-sm" style={{ background: p.accent }} />
                                            <span className="w-3 h-3 rounded-sm" style={{ background: p.secondary }} />
                                        </span>
                                        {p.name}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </section>

                    {/* Logo + Favicon */}
                    <section className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                        <h2 className="font-bold text-slate-900 flex items-center gap-2"><ImageIcon size={18}/> Logo & Favicon</h2>
                        <div className="grid sm:grid-cols-2 gap-4">
                            <div>
                                <div className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">Logo</div>
                                <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 flex items-center gap-3">
                                    {logoUrl ? (
                                        <img src={logoUrl} alt="logo" className="h-12 max-w-32 object-contain" />
                                    ) : (
                                        <div className="h-12 w-12 rounded bg-slate-100 grid place-items-center text-slate-400"><ImageIcon size={20}/></div>
                                    )}
                                    <button onClick={() => fileLogoRef.current?.click()}
                                        className="ml-auto inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-300 text-sm font-semibold hover:bg-slate-50"
                                        data-testid="branding-upload-logo-btn">
                                        <UploadSimple size={14}/> Upload
                                    </button>
                                    <input ref={fileLogoRef} type="file" accept="image/*" className="hidden"
                                        onChange={(e) => upload(e.target.files?.[0], "logo")} data-testid="branding-upload-logo-input"/>
                                </div>
                            </div>
                            <div>
                                <div className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">Favicon</div>
                                <div className="border-2 border-dashed border-slate-200 rounded-xl p-4 flex items-center gap-3">
                                    {faviconUrl ? (
                                        <img src={faviconUrl} alt="favicon" className="h-8 w-8 object-contain" />
                                    ) : (
                                        <div className="h-8 w-8 rounded bg-slate-100 grid place-items-center text-slate-400"><ImageIcon size={14}/></div>
                                    )}
                                    <button onClick={() => fileFaviconRef.current?.click()}
                                        className="ml-auto inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-300 text-sm font-semibold hover:bg-slate-50"
                                        data-testid="branding-upload-favicon-btn">
                                        <UploadSimple size={14}/> Upload
                                    </button>
                                    <input ref={fileFaviconRef} type="file" accept="image/*" className="hidden"
                                        onChange={(e) => upload(e.target.files?.[0], "favicon")} />
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Contact */}
                    <section className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                        <h2 className="font-bold text-slate-900 flex items-center gap-2"><EnvelopeSimple size={18}/> Contact & sender</h2>
                        <div className="grid sm:grid-cols-2 gap-3">
                            <label className="block">
                                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Support email</span>
                                <input type="email" value={form.support_email} onChange={(e) => set("support_email", e.target.value)}
                                    className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid="branding-support-email" />
                            </label>
                            <label className="block">
                                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Support phone</span>
                                <input type="tel" value={form.support_phone} onChange={(e) => set("support_phone", e.target.value)}
                                    className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid="branding-support-phone"/>
                            </label>
                            <label className="block sm:col-span-2">
                                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Email "from" name</span>
                                <input type="text" value={form.email_from_name} onChange={(e) => set("email_from_name", e.target.value)}
                                    placeholder="Defaults to your company name"
                                    className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid="branding-email-from"/>
                            </label>
                            <label className="block sm:col-span-2">
                                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Invoice footer</span>
                                <textarea rows={2} value={form.invoice_footer} onChange={(e) => set("invoice_footer", e.target.value)}
                                    className="mt-1 w-full px-3 py-2 rounded border border-slate-300 text-sm" data-testid="branding-invoice-footer"/>
                            </label>
                        </div>
                    </section>

                    {/* Custom domain */}
                    <section className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4">
                        <h2 className="font-bold text-slate-900 flex items-center gap-2"><Globe size={18}/> Custom domain</h2>
                        <label className="block">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Custom domain</span>
                            <input type="text" value={form.custom_domain} onChange={(e) => set("custom_domain", e.target.value)}
                                placeholder="app.acme.com"
                                className="mt-1 w-full h-10 px-3 rounded border border-slate-300 text-sm" data-testid="branding-domain"/>
                        </label>
                        {form.custom_domain && (
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-900">
                                <div className="font-bold mb-1">DNS setup</div>
                                <div>Add a <code className="bg-white px-1 rounded">CNAME</code> for <code className="bg-white px-1 rounded">{form.custom_domain}</code> → <code className="bg-white px-1 rounded">app.a1fieldpro.com</code></div>
                                <div className="mt-1 opacity-80">DNS can take up to 24h to propagate. Contact support to provision SSL.</div>
                            </div>
                        )}
                    </section>

                    <div className="flex justify-end">
                        <button onClick={save} disabled={saving}
                            className="px-6 py-3 rounded-xl font-bold text-white shadow-sm disabled:opacity-50"
                            style={{ background: form.primary_color }}
                            data-testid="branding-save-btn">
                            {saving ? "Saving…" : "Save branding"}
                        </button>
                    </div>
                </div>

                {/* Live preview */}
                <aside className="lg:sticky lg:top-4 space-y-4 h-fit">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Live preview</div>
                    <div className="rounded-2xl overflow-hidden border border-slate-200 shadow-lg">
                        <div className="px-4 py-3 flex items-center gap-2 text-white" style={{ background: form.primary_color }}>
                            {logoUrl ? <img src={logoUrl} alt="" className="h-7 max-w-24 object-contain"/> : (
                                <div className="font-extrabold tracking-tight">{form.app_name || "Your App"}</div>
                            )}
                            <div className="ml-auto text-xs opacity-90">Demo Owner</div>
                        </div>
                        <div className="p-4 bg-white space-y-3">
                            <div className="font-bold text-sm">{form.tagline || "A short tagline appears here."}</div>
                            <div className="flex gap-2">
                                <button className="px-3 py-2 rounded-lg text-white text-xs font-bold" style={{ background: form.primary_color }}>Primary action</button>
                                <button className="px-3 py-2 rounded-lg text-white text-xs font-bold" style={{ background: form.accent_color }}>Accent action</button>
                            </div>
                            <div className="border-l-4 pl-3 py-1 text-xs text-slate-700" style={{ borderColor: form.accent_color }}>
                                "Sample notification or alert"
                            </div>
                            <div className="text-[10px] text-slate-500 pt-2 border-t">
                                {form.invoice_footer || "Invoice footer preview"}
                            </div>
                        </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs space-y-2">
                        <div className="font-bold uppercase tracking-wider text-slate-600">Public booking URL</div>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 truncate bg-white px-2 py-1 rounded border">{`${window.location.origin}/book/${company?.id || ''}`}</code>
                            <button onClick={() => copy(`${window.location.origin}/book/${company?.id || ''}`, "URL")}
                                className="p-1.5 rounded hover:bg-slate-200" data-testid="copy-booking-url">
                                {copied === "URL" ? <Check size={14}/> : <Copy size={14}/>}
                            </button>
                        </div>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3 text-xs space-y-2" data-testid="public-landing-card">
                        <div className="font-bold uppercase tracking-wider text-slate-600">Your branded landing page</div>
                        <div className="text-slate-600">Auto-generated marketing site using your colors, logo, and contact info. Share with prospects.</div>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 truncate bg-white px-2 py-1 rounded border">{`${window.location.origin}/site/${company?.id || ''}`}</code>
                            <button onClick={() => copy(`${window.location.origin}/site/${company?.id || ''}`, "Landing URL")}
                                className="p-1.5 rounded hover:bg-slate-200" data-testid="copy-landing-url">
                                {copied === "Landing URL" ? <Check size={14}/> : <Copy size={14}/>}
                            </button>
                        </div>
                        <a href={`/site/${company?.id || ''}`} target="_blank" rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[#1D4ED8] font-semibold hover:underline"
                            data-testid="open-landing-link">
                            Open landing page →
                        </a>
                    </div>
                </aside>
            </div>
        </div>
    );
}
