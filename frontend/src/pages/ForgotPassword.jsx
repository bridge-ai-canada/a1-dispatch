import { useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { CheckCircle } from "@phosphor-icons/react";

export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [sent, setSent] = useState(null);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const { data } = await api.post("/auth/forgot", { email });
            setSent(data);
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail));
        } finally { setLoading(false); }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
            <div className="w-full max-w-sm">
                <div className="mb-8"><Brand /></div>
                <div className="border border-slate-200 bg-white p-8">
                    {sent ? (
                        <>
                            <CheckCircle size={36} weight="fill" className="text-emerald-500" />
                            <h1 className="font-display text-2xl font-extrabold tracking-tighter mt-3">Check your inbox</h1>
                            <p className="text-sm text-slate-600 mt-2">If an account exists for <strong>{email}</strong>, we sent a reset link.</p>
                            {sent.reset_url && (
                                <div className="mt-4 p-3 bg-blue-50 border-l-2 border-[#1D4ED8] text-xs text-slate-700 break-all" data-testid="reset-url-debug">
                                    <div className="overline mb-1">Dev preview</div>
                                    <a href={sent.reset_url} className="text-[#1D4ED8] underline font-mono">{sent.reset_url}</a>
                                </div>
                            )}
                            <Link to="/login" className="mt-6 inline-block text-sm text-[#1D4ED8] font-semibold hover:underline">← Back to sign in</Link>
                        </>
                    ) : (
                        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
                            <div className="overline">Reset</div>
                            <h1 className="font-display text-2xl font-extrabold tracking-tighter">Forgot password?</h1>
                            <p className="text-sm text-slate-600">Enter your email and we'll send a reset link.</p>
                            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@company.com" data-testid="forgot-email-input"
                                className="w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                            {error && <div className="text-sm text-[#DC2626]">{error}</div>}
                            <button type="submit" disabled={loading} data-testid="forgot-submit-button"
                                className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                                {loading ? "Sending..." : "Send reset link"}
                            </button>
                            <Link to="/login" className="block text-sm text-center text-slate-500 hover:text-slate-900">Back to sign in</Link>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
}
