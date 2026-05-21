import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { CheckCircle, FilePdf, ShieldCheck, CreditCard, Coins, SealCheck } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function fmtMoney(v) { return `$${(Number(v)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`; }

export default function PublicInvoice() {
    const { token } = useParams();
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [paying, setPaying] = useState(false);

    useEffect(() => {
        axios.get(`${API}/public/invoices/${token}`)
            .then((r) => setData(r.data))
            .catch(() => toast.error("Invoice not found"))
            .finally(() => setLoading(false));
    }, [token]);

    const pay = async (payType) => {
        setPaying(true);
        try {
            const r = await axios.post(`${API}/public/invoices/${token}/checkout`, {
                origin_url: window.location.origin, pay_type: payType,
            });
            window.location.href = r.data.url;
        } catch (e) {
            toast.error(e.response?.data?.detail || "Payment failed");
            setPaying(false);
        }
    };

    if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading invoice…</div>;
    if (!data) return <div className="min-h-screen flex items-center justify-center text-slate-500">Invoice not found.</div>;

    const { invoice, company } = data;
    const totals = invoice.totals || {};
    const paid = invoice.paid_amount || 0;
    const balance = invoice.balance_due || 0;
    const isPaid = balance <= 0.01;
    const primary = company?.branding?.primary_color || "#1D4ED8";

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900">
            <Toaster position="top-center" richColors/>
            <header className="bg-white border-b border-slate-200">
                <div className="max-w-3xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
                    <div>
                        <div className="text-xs font-bold uppercase tracking-widest" style={{ color: primary }}>
                            {company?.industry || "Service Pro"}
                        </div>
                        <div className="text-xl font-extrabold tracking-tight">{company?.name || "A1 Field Pro"}</div>
                    </div>
                </div>
            </header>

            <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
                {/* Title */}
                <div className="text-center mb-8">
                    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">{invoice.number}</div>
                    <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold tracking-tight">{invoice.title}</h1>
                    <p className="mt-1 text-slate-500">From <b>{company?.name}</b></p>
                    {isPaid ? (
                        <div className="mt-4 inline-flex items-center gap-2 bg-emerald-100 border border-emerald-300 text-emerald-800 px-4 py-2 rounded-full text-sm font-bold">
                            <SealCheck size={18} weight="fill"/> Paid in full · Thank you!
                        </div>
                    ) : (
                        <div className="mt-2 text-xs text-slate-500">Due {invoice.due_at ? new Date(invoice.due_at).toLocaleDateString() : "soon"}</div>
                    )}
                </div>

                {/* Big amount card */}
                <div className="rounded-3xl bg-white border border-slate-200 p-6 sm:p-8 shadow-sm">
                    <div className="text-center">
                        <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Amount due</div>
                        <div className="mt-2 text-5xl sm:text-6xl font-extrabold tracking-tight">{fmtMoney(balance)}</div>
                        {paid > 0 && !isPaid && (
                            <div className="mt-2 text-sm text-emerald-700 font-semibold">
                                <CheckCircle size={14} weight="fill" className="inline-block mr-1"/>
                                {fmtMoney(paid)} already paid
                            </div>
                        )}
                    </div>

                    {/* Action buttons */}
                    {!isPaid && (
                        <div className="mt-6 space-y-2">
                            {totals.deposit_amount > 0 && paid <= 0 && (
                                <button onClick={() => pay("deposit")} disabled={paying}
                                    className="w-full inline-flex items-center justify-center gap-2 bg-white border-2 border-emerald-300 hover:bg-emerald-50 text-emerald-800 font-bold py-4 rounded-xl text-base shadow-sm disabled:opacity-50"
                                    data-testid="pay-deposit-button">
                                    <Coins size={20}/> Pay deposit only ({fmtMoney(totals.deposit_amount)})
                                </button>
                            )}
                            <button onClick={() => pay(paid > 0 ? "balance" : "full")} disabled={paying}
                                className="w-full inline-flex items-center justify-center gap-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-bold py-4 rounded-xl text-base shadow-lg disabled:opacity-50"
                                data-testid="pay-balance-button">
                                <CreditCard size={20} weight="fill"/>
                                {paying ? "Redirecting…" : `Pay ${fmtMoney(balance)} now`}
                            </button>
                        </div>
                    )}
                    <div className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-500">
                        <ShieldCheck size={14}/> Secure payment via Stripe · Encrypted card details
                    </div>
                </div>

                {/* Line items */}
                <div className="mt-6 rounded-2xl bg-white border border-slate-200 overflow-hidden">
                    <div className="px-5 py-3 bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500 font-semibold">
                        Details
                    </div>
                    <table className="w-full text-sm">
                        <tbody>
                            {(invoice.line_items||[]).map((li, i) => (
                                <tr key={i} className="border-t border-slate-100">
                                    <td className="px-5 py-3">
                                        <div className="font-medium">{li.description}</div>
                                        <div className="text-xs text-slate-500">{li.qty} × {fmtMoney(li.unit_price)}</div>
                                    </td>
                                    <td className="px-5 py-3 text-right font-semibold">{fmtMoney((li.qty||0)*(li.unit_price||0))}</td>
                                </tr>
                            ))}
                            <tr className="border-t border-slate-200 bg-slate-50">
                                <td className="px-5 py-2 text-xs uppercase tracking-wider text-slate-500">Subtotal</td>
                                <td className="px-5 py-2 text-right">{fmtMoney(totals.subtotal)}</td>
                            </tr>
                            {totals.discount_amount > 0 && (
                                <tr className="bg-slate-50">
                                    <td className="px-5 py-1 text-xs uppercase tracking-wider text-slate-500">Discount</td>
                                    <td className="px-5 py-1 text-right text-emerald-700">-{fmtMoney(totals.discount_amount)}</td>
                                </tr>
                            )}
                            {totals.tax_amount > 0 && (
                                <tr className="bg-slate-50">
                                    <td className="px-5 py-1 text-xs uppercase tracking-wider text-slate-500">Tax</td>
                                    <td className="px-5 py-1 text-right">{fmtMoney(totals.tax_amount)}</td>
                                </tr>
                            )}
                            <tr className="bg-slate-900 text-white">
                                <td className="px-5 py-3 text-xs uppercase tracking-wider">Total</td>
                                <td className="px-5 py-3 text-right text-lg font-extrabold">{fmtMoney(totals.total)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                {invoice.terms && (
                    <div className="mt-6 text-xs text-slate-500 bg-white rounded-2xl border border-slate-200 p-5">
                        <div className="font-bold uppercase tracking-widest mb-1">Terms</div>
                        <p className="whitespace-pre-wrap">{invoice.terms}</p>
                    </div>
                )}
            </main>

            <footer className="text-center py-8 text-xs text-slate-400">
                Powered by A1 Field Pro
            </footer>
        </div>
    );
}
