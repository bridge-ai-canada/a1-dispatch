import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import Brand from "../components/Brand";
import { ShieldCheck, Copy } from "@phosphor-icons/react";

export default function SetupMFA() {
    const { user, refresh, logout } = useAuth();
    const navigate = useNavigate();
    const [setup, setSetup] = useState(null);
    const [code, setCode] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!user) return;
        if (user.mfa_enabled) { navigate("/app/dashboard"); return; }
        api.post("/auth/mfa/setup").then((r) => setSetup(r.data));
    }, [user, navigate]);

    const enable = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await api.post("/auth/mfa/enable", { code });
            await refresh();
            toast.success("Two-factor enabled");
            navigate("/app/dashboard");
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail));
        } finally { setLoading(false); }
    };

    const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success("Copied"); };

    if (!user) return null;

    return (
        <div className="min-h-screen bg-slate-50 p-6 flex items-center justify-center">
            <div className="w-full max-w-xl">
                <div className="flex items-center justify-between mb-8">
                    <Brand />
                    <button onClick={async () => { await logout(); navigate("/login"); }}
                        className="text-sm text-slate-500 hover:text-slate-900">Sign out</button>
                </div>
                <div className="bg-white border border-slate-200 p-8" data-testid="setup-mfa-page">
                    <div className="flex items-center gap-3">
                        <ShieldCheck size={28} weight="duotone" className="text-[#1D4ED8]" />
                        <div>
                            <div className="overline">Required</div>
                            <h1 className="font-display text-3xl font-extrabold tracking-tighter">Enable two-factor</h1>
                        </div>
                    </div>
                    <p className="text-sm text-slate-600 mt-4">
                        A1 Field Pro requires two-factor authentication for all accounts. Scan the QR code with
                        Google Authenticator, Authy, or 1Password, then enter the 6-digit code below.
                    </p>

                    {setup && (
                        <div className="grid sm:grid-cols-2 gap-6 mt-6">
                            <div className="border border-slate-200 p-4 flex flex-col items-center bg-slate-50">
                                <img src={setup.qr_data_url} alt="QR code" className="w-44 h-44" data-testid="mfa-qr" />
                            </div>
                            <div>
                                <div className="overline">Manual key</div>
                                <div className="mt-1 flex items-center gap-1">
                                    <div className="font-mono text-xs bg-slate-50 border border-slate-200 px-2 py-2 flex-1 break-all">{setup.secret}</div>
                                    <button onClick={() => copy(setup.secret)} className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><Copy size={14} /></button>
                                </div>

                                <form onSubmit={enable} className="mt-6 space-y-3">
                                    <div>
                                        <label className="text-xs font-medium">6-digit code</label>
                                        <input type="text" inputMode="numeric" maxLength={6} value={code}
                                            onChange={(e) => setCode(e.target.value.replace(/\D/g,""))}
                                            data-testid="mfa-verify-input"
                                            className="mt-1 w-full border border-slate-300 px-3 py-3 font-mono text-2xl tracking-widest text-center focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                                    </div>
                                    {error && <div className="text-sm text-[#DC2626]">{error}</div>}
                                    <button type="submit" disabled={loading || code.length < 6} data-testid="mfa-verify-button"
                                        className="w-full bg-[#DC2626] text-white font-semibold py-2.5 hover:bg-[#B91C1C] disabled:opacity-60">
                                        {loading ? "Verifying..." : "Enable two-factor"}
                                    </button>
                                </form>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
