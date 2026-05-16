import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { toast } from "sonner";
import { ShieldCheck } from "@phosphor-icons/react";

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [email, setEmail] = useState("demo@a1fieldpro.com");
    const [password, setPassword] = useState("Demo1234!");
    const [mfaCode, setMfaCode] = useState("");
    const [step, setStep] = useState("creds"); // creds | mfa
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const submitCreds = async (e) => {
        e?.preventDefault();
        setError("");
        setLoading(true);
        try {
            const user = await login(email, password);
            toast.success(`Welcome back, ${user.name}`);
            navigate(redirectFor(user));
        } catch (err) {
            const detail = err.response?.data?.detail;
            if (detail === "mfa_required") { setStep("mfa"); }
            else setError(formatApiError(detail) || err.message);
        } finally { setLoading(false); }
    };

    const submitMfa = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const user = await login(email, password, mfaCode);
            toast.success(`Welcome back, ${user.name}`);
            navigate(redirectFor(user));
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail) || "Invalid code");
        } finally { setLoading(false); }
    };

    return (
        <div className="min-h-screen grid lg:grid-cols-2">
            <div className="hidden lg:flex relative bg-slate-900 text-white p-12 flex-col justify-between">
                <Brand />
                <div>
                    <div className="overline text-slate-400">Field service ops</div>
                    <h2 className="font-display text-5xl font-extrabold tracking-tighter mt-3">
                        Welcome back to <span className="text-[#DC2626]">command</span>.
                    </h2>
                </div>
                <div className="text-xs text-slate-500">© 2026 A1 HVAC N DE-GO</div>
            </div>

            <div className="flex items-center justify-center p-8">
                <div className="w-full max-w-sm">
                    <div className="lg:hidden mb-10"><Brand /></div>
                    <div className="overline">Sign in</div>
                    <h1 className="font-display text-3xl font-extrabold tracking-tighter mt-2">
                        {step === "mfa" ? "Two-factor code" : "Field Pro account"}
                    </h1>

                    {step === "creds" ? (
                        <form onSubmit={submitCreds} className="mt-8 space-y-4" data-testid="login-form">
                            <div>
                                <label className="text-xs font-medium text-slate-700">Email</label>
                                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                                    data-testid="login-email-input"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-700">Password</label>
                                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                                    data-testid="login-password-input"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                                <Link to="/forgot" data-testid="forgot-link" className="block text-xs text-slate-500 hover:text-[#1D4ED8] mt-1.5">Forgot password?</Link>
                            </div>
                            {error && <ErrorBox text={error} />}
                            <button type="submit" disabled={loading} data-testid="login-submit-button"
                                className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                                {loading ? "Signing in..." : "Sign in"}
                            </button>
                        </form>
                    ) : (
                        <form onSubmit={submitMfa} className="mt-8 space-y-4" data-testid="mfa-form">
                            <div className="flex items-start gap-3 p-3 bg-blue-50 border-l-2 border-[#1D4ED8] text-sm">
                                <ShieldCheck size={20} className="text-[#1D4ED8] shrink-0 mt-0.5" />
                                <div>Enter the 6-digit code from your authenticator app.</div>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-700">Authentication code</label>
                                <input type="text" inputMode="numeric" maxLength={6} autoFocus required
                                    value={mfaCode} onChange={(e) => setMfaCode(e.target.value.replace(/\D/g,""))}
                                    data-testid="mfa-code-input"
                                    className="mt-1 w-full border border-slate-300 px-3 py-3 text-center font-mono text-2xl tracking-widest focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                            </div>
                            {error && <ErrorBox text={error} />}
                            <button type="submit" disabled={loading || mfaCode.length < 6} data-testid="mfa-submit-button"
                                className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                                {loading ? "Verifying..." : "Verify & sign in"}
                            </button>
                            <button type="button" onClick={() => { setStep("creds"); setMfaCode(""); setError(""); }}
                                className="w-full text-sm text-slate-500 hover:text-slate-900">Back</button>
                        </form>
                    )}

                    <div className="mt-6 text-sm text-slate-500">
                        No account? <Link to="/register" data-testid="link-to-register" className="text-[#1D4ED8] font-semibold hover:underline">Start free trial</Link>
                    </div>

                    <div className="mt-10 p-4 bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
                        <div className="overline mb-1">Demo accounts (password: Demo1234!)</div>
                        <div>Owner — demo@a1fieldpro.com</div>
                        <div>Dispatcher — dispatcher@a1fieldpro.com</div>
                        <div>Technician — tech@a1fieldpro.com</div>
                        <div className="mt-1 text-slate-500">Super Admin — superadmin@a1fieldpro.com / Super1234!</div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ErrorBox({ text }) {
    return <div data-testid="login-error" className="text-sm text-[#DC2626] border-l-2 border-[#DC2626] pl-3 py-1">{text}</div>;
}

export function redirectFor(user) {
    if (user.role === "super_admin") return "/app/admin/users";
    if (user.role === "technician")  return "/app/my-jobs";
    return "/app/dashboard";
}
