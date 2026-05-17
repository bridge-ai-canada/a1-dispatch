import { useState } from "react";
import { API_BASE } from "../lib/api";
import { Download, FileCsv, ChartLine } from "@phosphor-icons/react";

const EXPORTS = [
    { id: "jobs", label: "Work Orders", desc: "Every job with status, price, tip, rating, payment status.", path: "/exports/jobs.csv" },
    { id: "customers", label: "Customers", desc: "CRM records with tags, contact info, and notes.", path: "/exports/customers.csv" },
    { id: "payments", label: "Payments", desc: "Stripe transactions, including tip checkouts.", path: "/exports/payments.csv" },
];

function isoDate(d) { return d ? new Date(d).toISOString().slice(0, 10) : ""; }

export default function Reports() {
    const today = new Date();
    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    const [from, setFrom] = useState(isoDate(monthStart));
    const [to, setTo] = useState(isoDate(today));

    const buildUrl = (path) => {
        const params = new URLSearchParams();
        if (from) params.set("from", from);
        if (to) params.set("to", to + "T23:59:59"); // inclusive
        return `${API_BASE}${path}?${params.toString()}`;
    };

    return (
        <div data-testid="reports-page" className="space-y-6">
            <div>
                <div className="overline">Insights</div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Reports & Exports</h1>
                <p className="text-sm text-slate-500 mt-2">
                    Download CSV files for QuickBooks, Excel, or your accountant. Filter by date range.
                </p>
            </div>

            <div className="border border-slate-200 p-5 bg-white">
                <div className="overline mb-3 flex items-center gap-1.5"><ChartLine size={12} /> Date range</div>
                <div className="grid sm:grid-cols-2 gap-3 max-w-md">
                    <div>
                        <label className="text-xs font-medium">From</label>
                        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} data-testid="reports-from"
                            className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    </div>
                    <div>
                        <label className="text-xs font-medium">To</label>
                        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} data-testid="reports-to"
                            className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    </div>
                </div>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {EXPORTS.map((e) => (
                    <div key={e.id} data-testid={`export-card-${e.id}`}
                        className="border border-slate-200 p-5 bg-white hover:border-[#1D4ED8] transition-colors">
                        <div className="flex items-center gap-2.5">
                            <FileCsv size={26} weight="duotone" className="text-[#1D4ED8]" />
                            <div className="font-display text-xl font-extrabold tracking-tight">{e.label}</div>
                        </div>
                        <p className="text-sm text-slate-600 mt-2 min-h-[40px]">{e.desc}</p>
                        <a href={buildUrl(e.path)} target="_blank" rel="noopener noreferrer"
                            data-testid={`export-download-${e.id}`}
                            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-[#1D4ED8] text-white text-sm font-semibold hover:opacity-90">
                            <Download size={14} weight="bold" /> Download CSV
                        </a>
                    </div>
                ))}
            </div>

            <p className="text-xs text-slate-400">
                Downloads use your active session cookie. Owner and accountant roles only.
            </p>
        </div>
    );
}
