import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import api, { API_BASE, formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { toast } from "sonner";
import { Copy, UploadSimple, Check, ShieldCheck, ShieldSlash, Trash, DeviceMobile } from "@phosphor-icons/react";

const COLOR_PRESETS = [
    { name: "Signal Red",   primary: "#1D4ED8", accent: "#DC2626" },
    { name: "Forest Green", primary: "#15803D", accent: "#F97316" },
    { name: "Royal Purple", primary: "#7C3AED", accent: "#F59E0B" },
    { name: "Charcoal",     primary: "#0F172A", accent: "#EAB308" },
    { name: "Ocean",        primary: "#0E7490", accent: "#DC2626" },
];

export default function Settings() {
    const { user, company, refresh } = useAuth();
    const fileInput = useRef(null);
    const [primary, setPrimary] = useState("#1D4ED8");
    const [accent, setAccent] = useState("#DC2626");
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (company?.branding) {
            setPrimary(company.branding.primary_color || "#1D4ED8");
            setAccent(company.branding.accent_color || "#DC2626");
        }
    }, [company]);

    const bookingUrl = company ? `${window.location.origin}/book/${company.id}` : "";
    const embedSnippet = `<iframe src="${bookingUrl}" width="100%" height="800" frameborder="0" style="border:0"></iframe>`;

    const copy = (txt, label) => { navigator.clipboard.writeText(txt); toast.success(`${label} copied`); };

    const saveBranding = async () => {
        setSaving(true);
        try {
            await api.patch("/companies/me", { primary_color: primary, accent_color: accent });
            await refresh();
            toast.success("Branding saved");
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        } finally { setSaving(false); }
    };

    const uploadLogo = async (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        const fd = new FormData(); fd.append("file", f);
        try {
            await api.post("/companies/me/logo", fd, { headers: { "Content-Type": "multipart/form-data" }});
            await refresh();
            toast.success("Logo uploaded");
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
        e.target.value = "";
    };

    const logoUrl = company?.branding?.logo_path ? `${API_BASE}/files/${company.branding.logo_path}` : null;

    return (
        <div data-testid="settings-page" className="space-y-8 max-w-3xl">
            <div>
                <div className="overline">Workspace</div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Settings</h1>
            </div>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Company</div>
                <div className="flex items-center gap-4 mb-6"><Brand size="lg" /></div>
                <div className="grid sm:grid-cols-2 gap-6 text-sm">
                    <Field label="Company name" value={company?.name} />
                    <Field label="Industry" value={company?.industry} />
                    <Field label="Owner" value={user?.name} />
                    <Field label="Email" value={user?.email} />
                </div>
            </section>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">White-label branding</div>

                <div className="mb-6">
                    <div className="text-xs font-medium mb-2">Logo</div>
                    <div className="flex items-center gap-4">
                        <div className="h-20 w-20 border border-slate-300 flex items-center justify-center bg-slate-50">
                            {logoUrl ? <img src={logoUrl} alt="logo" className="max-h-full max-w-full object-contain" /> : <span className="text-xs text-slate-400">No logo</span>}
                        </div>
                        <input type="file" accept="image/*" ref={fileInput} className="hidden" onChange={uploadLogo} data-testid="logo-upload-input" />
                        <button onClick={() => fileInput.current?.click()} data-testid="upload-logo-button"
                            className="flex items-center gap-1.5 px-4 py-2 border border-slate-300 hover:bg-slate-50 text-sm font-medium">
                            <UploadSimple size={14} /> Upload logo
                        </button>
                    </div>
                </div>

                <div className="text-xs font-medium mb-2">Color presets</div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-6">
                    {COLOR_PRESETS.map((p) => (
                        <button key={p.name} type="button" onClick={() => { setPrimary(p.primary); setAccent(p.accent); }}
                            data-testid={`preset-${p.name.replace(/\s+/g,"-").toLowerCase()}`}
                            className={`p-2 border text-left text-xs ${primary === p.primary && accent === p.accent ? "border-slate-900" : "border-slate-200 hover:border-slate-400"}`}>
                            <div className="flex gap-1 mb-1">
                                <span className="h-4 w-4" style={{ background: p.primary }} />
                                <span className="h-4 w-4" style={{ background: p.accent }} />
                            </div>
                            <div className="font-medium truncate">{p.name}</div>
                        </button>
                    ))}
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <div className="text-xs font-medium mb-1">Primary color</div>
                        <div className="flex items-center gap-2">
                            <input type="color" value={primary} onChange={(e) => setPrimary(e.target.value)} data-testid="primary-color-input"
                                className="h-10 w-12 border border-slate-300 cursor-pointer" />
                            <input value={primary} onChange={(e) => setPrimary(e.target.value)}
                                className="flex-1 border border-slate-300 px-2 py-2 font-mono text-sm" />
                        </div>
                    </div>
                    <div>
                        <div className="text-xs font-medium mb-1">Accent color</div>
                        <div className="flex items-center gap-2">
                            <input type="color" value={accent} onChange={(e) => setAccent(e.target.value)} data-testid="accent-color-input"
                                className="h-10 w-12 border border-slate-300 cursor-pointer" />
                            <input value={accent} onChange={(e) => setAccent(e.target.value)}
                                className="flex-1 border border-slate-300 px-2 py-2 font-mono text-sm" />
                        </div>
                    </div>
                </div>

                <button onClick={saveBranding} disabled={saving} data-testid="save-branding-button"
                    className="mt-4 flex items-center gap-1.5 bg-slate-900 text-white px-5 py-2 font-semibold hover:bg-slate-800 disabled:opacity-60">
                    <Check size={14} /> {saving ? "Saving..." : "Save branding"}
                </button>
            </section>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Online booking widget</div>
                <p className="text-sm text-slate-600">Share this link or paste the embed snippet on your website.</p>

                <div className="mt-4">
                    <div className="text-xs font-medium mb-1">Direct link</div>
                    <div className="flex items-center gap-2">
                        <input readOnly value={bookingUrl} data-testid="booking-link-input"
                            className="flex-1 border border-slate-300 px-3 py-2 font-mono text-xs bg-slate-50" />
                        <button onClick={() => copy(bookingUrl, "Link")} data-testid="copy-booking-link-button"
                            className="flex items-center gap-1 px-3 py-2 border border-slate-300 hover:bg-slate-50 text-sm font-medium">
                            <Copy size={14} /> Copy
                        </button>
                        <a href={bookingUrl} target="_blank" rel="noopener noreferrer" data-testid="open-booking-link"
                            className="px-3 py-2 bg-[#1D4ED8] text-white text-sm font-semibold hover:bg-[#1E40AF]">Open</a>
                    </div>
                </div>

                <div className="mt-4">
                    <div className="text-xs font-medium mb-1">Embed snippet</div>
                    <div className="flex items-start gap-2">
                        <textarea readOnly value={embedSnippet} rows={3} data-testid="embed-snippet"
                            className="flex-1 border border-slate-300 px-3 py-2 font-mono text-xs bg-slate-50" />
                        <button onClick={() => copy(embedSnippet, "Embed snippet")} data-testid="copy-embed-button"
                            className="flex items-center gap-1 px-3 py-2 border border-slate-300 hover:bg-slate-50 text-sm font-medium">
                            <Copy size={14} /> Copy
                        </button>
                    </div>
                </div>
            </section>

            <SecuritySection />
            <SessionsSection />

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Plan</div>
                <div className="flex items-center justify-between">
                    <div>
                        <div className="font-display text-2xl font-extrabold tracking-tighter">Pro · Trial</div>
                        <div className="text-sm text-slate-500 mt-1">14 days remaining</div>
                    </div>
                    <button className="bg-[#1D4ED8] text-white px-5 py-2.5 font-semibold hover:bg-[#1E40AF]">Upgrade</button>
                </div>
            </section>
        </div>
    );
}

function Field({ label, value }) {
    return (
        <div>
            <div className="overline mb-1">{label}</div>
            <div className="font-medium">{value || "—"}</div>
        </div>
    );
}

function SecuritySection() {
    const { user, refresh } = useAuth();
    const [setup, setSetup] = useState(null);
    const [code, setCode] = useState("");
    const [pw, setPw] = useState("");

    const startEnroll = async () => {
        const { data } = await api.post("/auth/mfa/setup");
        setSetup(data);
    };
    const enable = async () => {
        try {
            await api.post("/auth/mfa/enable", { code });
            await refresh();
            toast.success("Two-factor enabled");
            setSetup(null); setCode("");
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
    };
    const disable = async () => {
        try {
            await api.post("/auth/mfa/disable", { password: pw });
            await refresh();
            toast.success("Two-factor disabled");
            setPw("");
        } catch (err) { toast.error(formatApiError(err.response?.data?.detail)); }
    };

    return (
        <section className="border border-slate-200 p-6" data-testid="security-section">
            <div className="overline mb-3">Security · Two-factor</div>
            {user?.mfa_enabled ? (
                <div>
                    <div className="flex items-center gap-2 text-sm text-emerald-700">
                        <ShieldCheck size={18} weight="fill" /> Two-factor authentication is enabled.
                    </div>
                    <div className="mt-4 grid sm:grid-cols-[1fr_auto] gap-2 max-w-md">
                        <input type="password" placeholder="Enter your password to disable" value={pw} onChange={(e) => setPw(e.target.value)}
                            data-testid="mfa-disable-pw" className="border border-slate-300 px-3 py-2" />
                        <button onClick={disable} disabled={!pw} data-testid="mfa-disable-button"
                            className="px-4 py-2 border border-[#DC2626] text-[#DC2626] hover:bg-red-50 font-semibold disabled:opacity-50">
                            <ShieldSlash size={14} className="inline mr-1" /> Disable
                        </button>
                    </div>
                </div>
            ) : setup ? (
                <div className="grid sm:grid-cols-2 gap-6">
                    <div className="border border-slate-200 p-3 bg-slate-50 flex items-center justify-center">
                        <img src={setup.qr_data_url} alt="QR" className="w-44 h-44" />
                    </div>
                    <div className="space-y-3">
                        <p className="text-sm text-slate-600">Scan with your authenticator and enter the 6-digit code.</p>
                        <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g,""))}
                            maxLength={6} inputMode="numeric" data-testid="settings-mfa-code"
                            className="w-full border border-slate-300 px-3 py-3 text-center font-mono text-2xl tracking-widest" />
                        <button onClick={enable} disabled={code.length < 6} data-testid="settings-mfa-enable"
                            className="w-full bg-[#DC2626] text-white py-2.5 font-semibold hover:bg-[#B91C1C] disabled:opacity-50">
                            Enable
                        </button>
                    </div>
                </div>
            ) : (
                <div>
                    <div className="flex items-center gap-2 text-sm text-slate-500">
                        <ShieldSlash size={18} /> Not enabled.
                    </div>
                    <button onClick={startEnroll} data-testid="settings-mfa-start"
                        className="mt-3 px-4 py-2 bg-[#1D4ED8] text-white font-semibold hover:bg-[#1E40AF]">
                        Enable two-factor
                    </button>
                </div>
            )}
        </section>
    );
}

function SessionsSection() {
    const [sessions, setSessions] = useState([]);
    const load = () => api.get("/sessions").then((r) => setSessions(r.data));
    useEffect(() => { load(); }, []);
    const revoke = async (id) => {
        try { await api.delete(`/sessions/${id}`); toast.success("Session revoked"); load(); }
        catch { toast.error("Could not revoke"); }
    };
    return (
        <section className="border border-slate-200 p-6" data-testid="sessions-section">
            <div className="overline mb-3">Active sessions</div>
            <div className="divide-y divide-slate-200">
                {sessions.map((s) => (
                    <div key={s.id} className="py-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                            <DeviceMobile size={18} className="text-slate-400 shrink-0" />
                            <div className="min-w-0">
                                <div className="text-sm font-medium truncate">{s.user_agent || "Unknown device"}</div>
                                <div className="text-xs text-slate-500">{new Date(s.created_at).toLocaleString()} · {s.ip || "—"}</div>
                            </div>
                        </div>
                        {s.current ? (
                            <span className="text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-700 font-semibold uppercase tracking-wider">This device</span>
                        ) : (
                            <button onClick={() => revoke(s.id)} data-testid={`revoke-session-${s.id}`}
                                className="text-xs px-2 py-1 border border-slate-300 hover:bg-slate-50 inline-flex items-center gap-1">
                                <Trash size={12} /> Revoke
                            </button>
                        )}
                    </div>
                ))}
            </div>
        </section>
    );
}
