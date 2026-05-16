import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { toast } from "sonner";
import { GoogleLogo } from "@phosphor-icons/react";
import { startGoogleLogin } from "./AuthCallback";

const INDUSTRIES = ["HVAC", "Plumbing", "Electrical", "Garage Doors", "Roofing", "Appliance Repair", "Home Services"];

export default function Register() {
    const { register } = useAuth();
    const navigate = useNavigate();
    const [form, setForm] = useState({
        company_name: "", industry: "HVAC", name: "", email: "", password: "",
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const onSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            const user = await register(form);
            toast.success(`Welcome, ${user.name}!`);
            navigate("/app/dashboard");
        } catch (err) {
            setError(formatApiError(err.response?.data?.detail) || err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen grid lg:grid-cols-2">
            <div className="flex items-center justify-center p-8 order-2 lg:order-1">
                <div className="w-full max-w-md">
                    <div className="lg:hidden mb-10"><Brand /></div>
                    <div className="overline">Start free trial</div>
                    <h1 className="font-display text-3xl font-extrabold tracking-tighter mt-2">Create your A1 Field Pro account</h1>
                    <p className="text-sm text-slate-500 mt-2">14-day free trial. No credit card required.</p>

                    <button onClick={() => startGoogleLogin("/auth/callback")} type="button" data-testid="register-google-button"
                        className="mt-6 w-full flex items-center justify-center gap-2 border border-slate-300 px-4 py-2.5 hover:bg-slate-50 font-semibold text-sm">
                        <GoogleLogo size={18} weight="bold" /> Continue with Google
                    </button>
                    <p className="mt-1 text-xs text-slate-500">New Google accounts default to <strong>Customer</strong> role — perfect for homeowners.</p>

                    <form onSubmit={onSubmit} className="mt-8 space-y-4" data-testid="register-form">
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-medium text-slate-700">Company</label>
                                <input
                                    required value={form.company_name} onChange={update("company_name")}
                                    data-testid="register-company-input"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
                                    placeholder="A1 HVAC N DE-GO"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-slate-700">Industry</label>
                                <select
                                    value={form.industry} onChange={update("industry")}
                                    data-testid="register-industry-select"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
                                >
                                    {INDUSTRIES.map((i) => <option key={i}>{i}</option>)}
                                </select>
                            </div>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-700">Your name</label>
                            <input
                                required value={form.name} onChange={update("name")}
                                data-testid="register-name-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-700">Work email</label>
                            <input
                                type="email" required value={form.email} onChange={update("email")}
                                data-testid="register-email-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-700">Password</label>
                            <input
                                type="password" required minLength={6} value={form.password} onChange={update("password")}
                                data-testid="register-password-input"
                                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
                            />
                        </div>
                        {error && (
                            <div data-testid="register-error" className="text-sm text-[#DC2626] border-l-2 border-[#DC2626] pl-3 py-1">
                                {error}
                            </div>
                        )}
                        <button
                            type="submit"
                            disabled={loading}
                            data-testid="register-submit-button"
                            className="w-full bg-[#DC2626] text-white font-semibold py-2.5 hover:bg-[#B91C1C] disabled:opacity-60 transition-colors"
                        >
                            {loading ? "Creating..." : "Create account"}
                        </button>
                    </form>

                    <div className="mt-6 text-sm text-slate-500">
                        Already have an account?{" "}
                        <Link to="/login" data-testid="link-to-login" className="text-[#1D4ED8] font-semibold hover:underline">Sign in</Link>
                    </div>
                </div>
            </div>

            <div className="hidden lg:flex relative bg-[#1D4ED8] text-white p-12 flex-col justify-between order-1 lg:order-2">
                <div className="flex justify-between"><Brand /> <div className="overline text-white/70">14-day trial</div></div>
                <div>
                    <h2 className="font-display text-5xl font-extrabold tracking-tighter">
                        Built for crews <br />that <span className="text-[#FCD34D]">close jobs</span>.
                    </h2>
                    <p className="mt-6 text-white/80 leading-relaxed max-w-md">
                        Spin up your company, invite your dispatchers and techs, and start dispatching
                        work orders in under five minutes.
                    </p>
                </div>
                <div className="text-xs text-white/60">© 2026 A1 HVAC N DE-GO</div>
            </div>
        </div>
    );
}
