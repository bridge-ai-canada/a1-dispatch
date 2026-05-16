import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import api from "../lib/api";
import { CheckCircle, XCircle, CircleNotch } from "@phosphor-icons/react";

export default function PaymentResult() {
    const [params] = useSearchParams();
    const sessionId = params.get("session_id");
    const [status, setStatus] = useState("checking");
    const [tx, setTx] = useState(null);

    useEffect(() => {
        if (!sessionId) { setStatus("missing"); return; }
        let attempts = 0;
        const poll = async () => {
            try {
                const { data } = await api.get(`/payments/status/${sessionId}`);
                setTx(data);
                if (data.payment_status === "paid") { setStatus("paid"); return; }
                if (data.status === "expired") { setStatus("expired"); return; }
                if (attempts++ < 6) setTimeout(poll, 2000);
                else setStatus("pending");
            } catch {
                setStatus("error");
            }
        };
        poll();
    }, [sessionId]);

    const meta = {
        checking: { icon: CircleNotch, title: "Confirming payment...", color: "text-[#1D4ED8] animate-spin" },
        paid:     { icon: CheckCircle, title: "Payment received", color: "text-emerald-600" },
        expired:  { icon: XCircle, title: "Session expired", color: "text-[#DC2626]" },
        pending:  { icon: CircleNotch, title: "Still processing", color: "text-amber-600" },
        error:    { icon: XCircle, title: "Error verifying payment", color: "text-[#DC2626]" },
        missing:  { icon: XCircle, title: "No session", color: "text-[#DC2626]" },
    }[status];

    const Icon = meta.icon;
    return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
            <div className="bg-white border border-slate-200 p-10 max-w-md w-full text-center" data-testid="payment-result">
                <Icon size={48} weight="fill" className={`${meta.color} mx-auto`} />
                <h1 className="font-display text-3xl font-extrabold tracking-tighter mt-4">{meta.title}</h1>
                {tx && (
                    <div className="mt-4 text-slate-600">
                        ${tx.amount.toFixed(2)} {tx.currency.toUpperCase()}
                    </div>
                )}
                <Link to="/app/jobs" data-testid="back-to-jobs-link"
                    className="mt-8 inline-block bg-[#1D4ED8] text-white font-semibold px-6 py-2.5 hover:bg-[#1E40AF]">
                    Back to jobs
                </Link>
            </div>
        </div>
    );
}
