import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { toast } from "sonner";

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [email, setEmail] = useState("demo@a1fieldpro.com");
    const [password, setPassword] = useState("Demo1234!");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const user = await login(email, password);
            toast.success(`Welcome back, ${user.name}`);
            navigate(user.role === "technician" ? "/app/my-jobs" : "/app/dashboard");
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail) || err.message);
        } finally {
            setLoading(false);
        }
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
                    <p className="mt-6 text-slate-300 max-w-md leading-relaxed">
                        Pick up exactly where you left off. Your team, your jobs, your revenue —
                        all in one place.
                    </p>
                </div>
                <div className="text-xs text-slate-500">© 2026 A1 HVAC N DE-GO</div>
            </div>

            <div className="flex items-center justify-center p-8">
                <div className="w-full max-w-sm">
                    <div className="lg:hidden mb-10"><Brand /></div>
                    <div className="overline">Sign in</div>
                    <h1 className="font-display text-3xl font-extrabold tracking-tighter mt-2">Field Pro account</h1>

                    <form onSubmit={onSubmit} className="mt-8 space-y-4" data-testid="login-form">
                        <div>
                            <label className="text-xs font-medium text-slate-700">Email</label>
                            <input
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                data-testid="login-email-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] focus:border-[#1D4ED8]"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-700">Password</label>
                            <input
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                data-testid="login-password-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] focus:border-[#1D4ED8]"
                            />
                        </div>
                        {error && (
                            <div data-testid="login-error" className="text-sm text-[#DC2626] border-l-2 border-[#DC2626] pl-3 py-1">
                                {error}
                            </div>
                        )}
                        <button
                            type="submit"
                            disabled={loading}
                            data-testid="login-submit-button"
                            className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60 transition-colors"
                        >
                            {loading ? "Signing in..." : "Sign in"}
                        </button>
                    </form>

                    <div className="mt-6 text-sm text-slate-500">
                        No account?{" "}
                        <Link to="/register" data-testid="link-to-register" className="text-[#1D4ED8] font-semibold hover:underline">
                            Start free trial
                        </Link>
                    </div>

                    <div className="mt-10 p-4 bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
                        <div className="overline mb-1">Demo accounts</div>
                        <div>Owner — demo@a1fieldpro.com</div>
                        <div>Dispatcher — dispatcher@a1fieldpro.com</div>
                        <div>Technician — tech@a1fieldpro.com</div>
                        <div className="mt-1 font-medium">Password: Demo1234!</div>
                    </div>
                </div>
            </div>
        </div>
    );
}
