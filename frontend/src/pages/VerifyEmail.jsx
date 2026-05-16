import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import Brand from "../components/Brand";
import { CheckCircle, XCircle, CircleNotch } from "@phosphor-icons/react";

export default function VerifyEmail() {
    const [params] = useSearchParams();
    const token = params.get("token") || "";
    const [status, setStatus] = useState("loading"); // loading | ok | error
    const [error, setError] = useState("");

    useEffect(() => {
        if (!token) { setStatus("error"); setError("Missing token"); return; }
        api.post(`/auth/verify?token=${encodeURIComponent(token)}`)
            .then(() => setStatus("ok"))
            .catch((err) => { setStatus("error"); setError(formatApiError(err.response?.data?.detail)); });
    }, [token]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
            <div className="bg-white border border-slate-200 p-10 max-w-md w-full text-center">
                <div className="mb-6"><Brand /></div>
                {status === "loading" && <CircleNotch size={48} className="text-[#1D4ED8] mx-auto animate-spin" />}
                {status === "ok" && (
                    <>
                        <CheckCircle size={48} weight="fill" className="text-emerald-500 mx-auto" />
                        <h1 className="font-display text-2xl font-extrabold tracking-tighter mt-4">Email verified</h1>
                        <p className="text-slate-600 mt-2 text-sm">You can now receive invoices and booking confirmations.</p>
                    </>
                )}
                {status === "error" && (
                    <>
                        <XCircle size={48} weight="fill" className="text-[#DC2626] mx-auto" />
                        <h1 className="font-display text-2xl font-extrabold tracking-tighter mt-4">Verification failed</h1>
                        <p className="text-slate-600 mt-2 text-sm">{error}</p>
                    </>
                )}
                <Link to="/" className="mt-6 inline-block text-sm font-semibold text-[#1D4ED8] hover:underline">Continue to A1 Field Pro →</Link>
            </div>
        </div>
    );
}
