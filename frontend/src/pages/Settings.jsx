import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";

export default function Settings() {
    const { user, company } = useAuth();
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
