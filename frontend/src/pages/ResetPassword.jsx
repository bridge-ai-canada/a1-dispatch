import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { toast } from "sonner";

export default function ResetPassword() {
    const [params] = useSearchParams();
    const token = params.get("token") || "";
    const invited = params.get("invited") === "1";
    const navigate = useNavigate();
    const [pw, setPw] = useState("");
    const [pw2, setPw2] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        if (pw.length < 6) { setError("Password must be at least 6 characters."); return; }
        if (pw !== pw2) { setError("Passwords don't match."); return; }
        setLoading(true);
        try {
            await api.post("/auth/reset", { token, new_password: pw });
            toast.success("Password updated. Please sign in.");
            navigate("/login");
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail));
        } finally { setLoading(false); }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
            <div className="w-full max-w-sm">
                <div className="mb-8"><Brand /></div>
                <form onSubmit={submit} className="border border-slate-200 bg-white p-8 space-y-4" data-testid="reset-form">
                    <div className="overline">{invited ? "Welcome" : "Reset"}</div>
                    <h1 className="font-display text-2xl font-extrabold tracking-tighter">
                        {invited ? "Set your password" : "New password"}
                    </h1>
                    {!token && <div className="text-sm text-[#DC2626]">Missing or invalid token.</div>}
                    <div>
                        <label className="text-xs font-medium">New password</label>
                        <input type="password" required value={pw} onChange={(e) => setPw(e.target.value)}
                            data-testid="reset-password-input"
                            className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    </div>
                    <div>
                        <label className="text-xs font-medium">Confirm</label>
                        <input type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)}
                            data-testid="reset-confirm-input"
                            className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    </div>
                    {error && <div className="text-sm text-[#DC2626]">{error}</div>}
                    <button type="submit" disabled={loading || !token} data-testid="reset-submit-button"
                        className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                        {loading ? "Saving..." : "Save password"}
                    </button>
                    <Link to="/login" className="block text-sm text-center text-slate-500 hover:text-slate-900">Sign in</Link>
                </form>
            </div>
        </div>
    );
}
