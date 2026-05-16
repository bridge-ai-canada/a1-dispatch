import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import { toast } from "sonner";
import { Copy } from "@phosphor-icons/react";

export default function Settings() {
    const { user, company } = useAuth();
    const bookingUrl = company ? `${window.location.origin}/book/${company.id}` : "";
    const copy = () => {
        navigator.clipboard.writeText(bookingUrl);
        toast.success("Booking link copied");
    };
    return (
        <div data-testid="settings-page" className="space-y-8 max-w-3xl">
            <div>
                <div className="overline">Workspace</div>
                <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Settings</h1>
            </div>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Company</div>
                <div className="flex items-center gap-4 mb-6"><Brand size="lg" /></div>
                <div className="grid sm:grid-cols-2 gap-6 text-sm">
                    <Field label="Company name" value={company?.name} />
                    <Field label="Industry" value={company?.industry} />
                    <Field label="Owner" value={user?.name} />
                    <Field label="Email" value={user?.email} />
                </div>
            </section>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Online booking widget</div>
                <p className="text-sm text-slate-600">
                    Share this link or embed it on your website. Customers submit a request and a job is auto-created in your queue.
                </p>
                <div className="mt-4 flex items-center gap-2">
                    <input readOnly value={bookingUrl} data-testid="booking-link-input"
                        className="flex-1 border border-slate-300 px-3 py-2 font-mono text-sm bg-slate-50" />
                    <button onClick={copy} data-testid="copy-booking-link-button"
                        className="flex items-center gap-1 px-3 py-2 border border-slate-300 hover:bg-slate-50 text-sm font-medium">
                        <Copy size={14} /> Copy
                    </button>
                    <a href={bookingUrl} target="_blank" rel="noopener noreferrer" data-testid="open-booking-link"
                        className="px-3 py-2 bg-[#1D4ED8] text-white text-sm font-semibold hover:bg-[#1E40AF]">Open</a>
                </div>
            </section>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Branding (white-label)</div>
                <p className="text-sm text-slate-600">
                    Customize logo, colors, and customer-facing emails. Available on Pro plan.
                </p>
                <button disabled data-testid="branding-disabled-button"
                    className="mt-4 px-4 py-2 border border-slate-300 text-slate-400 cursor-not-allowed">
                    Coming soon
                </button>
            </section>

            <section className="border border-slate-200 p-6">
                <div className="overline mb-3">Plan</div>
                <div className="flex items-center justify-between">
                    <div>
                        <div className="font-display text-2xl font-extrabold tracking-tighter">Pro · Trial</div>
                        <div className="text-sm text-slate-500 mt-1">14 days remaining</div>
                    </div>
                    <button className="bg-[#1D4ED8] text-white px-5 py-2.5 font-semibold hover:bg-[#1E40AF]">Upgrade</button>
                </div>
            </section>
        </div>
    );
}

function Field({ label, value }) {
    return (
        <div>
            <div className="overline mb-1">{label}</div>
            <div className="font-medium">{value || "—"}</div>
        </div>
    );
}
