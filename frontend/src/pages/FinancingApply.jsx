import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API_BASE } from "../lib/api";
import SignaturePad from "../components/SignaturePad";
import { CheckCircle, XCircle, Clock, ShieldCheck, CurrencyDollar, Calendar, Info } from "@phosphor-icons/react";

const fmt$ = (v) => `$${(Number(v) || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;

export default function FinancingApply() {
    const { token } = useParams();
    const [data, setData] = useState(null);
    const [err, setErr] = useState("");
    const [step, setStep] = useState(1);   // 1=form, 2=decision, 3=sign, 4=signed
    const [submitting, setSubmitting] = useState(false);
    const [decision, setDecision] = useState(null);
    const [signing, setSigning] = useState(false);
    const [signerName, setSignerName] = useState("");
    const [signatureB64, setSignatureB64] = useState("");
    const [form, setForm] = useState({
        first_name: "", last_name: "", email: "", phone: "",
        dob: "", ssn4: "",
        fico_bucket: "good",
        monthly_income: "", monthly_obligations: "",
        employment_status: "full_time",
        consent_soft_pull: false,
    });

    useEffect(() => {
        axios.get(`${API_BASE}/public/financing/${token}`)
            .then(({ data }) => {
                setData(data);
                const a = data.application || {};
                if (["decisioned", "manual_review"].includes(a.status)) {
                    setDecision({ decision: a.decision, offer: a.offer, tier_label: (a.tier || {}).label, reason: a.decision_reason });
                    setStep(2);
                } else if (["signed", "funded"].includes(a.status)) {
                    setStep(4);
                }
            })
            .catch((e) => setErr(e.response?.data?.detail || "Application not found"));
    }, [token]);

    const submit = async () => {
        if (!form.consent_soft_pull) { alert("Please consent to the soft credit check"); return; }
        setSubmitting(true);
        try {
            const { data: d } = await axios.post(`${API_BASE}/public/financing/${token}/submit`, {
                ...form,
                monthly_income: Number(form.monthly_income || 0),
                monthly_obligations: Number(form.monthly_obligations || 0),
            });
            setDecision(d);
            setStep(2);
        } catch (e) {
            alert(e.response?.data?.detail || "Submission failed");
        } finally { setSubmitting(false); }
    };

    const sign = async () => {
        if (!signerName || !signatureB64) { alert("Please type your name and sign"); return; }
        setSigning(true);
        try {
            await axios.post(`${API_BASE}/public/financing/${token}/sign`, {
                signer_name: signerName, signature_base64: signatureB64,
            });
            setStep(4);
        } catch (e) {
            alert(e.response?.data?.detail || "Signing failed");
        } finally { setSigning(false); }
    };

    if (err) return <div className="min-h-screen grid place-items-center text-center p-6"><div className="space-y-2"><XCircle size={48} className="mx-auto text-rose-500"/><h1 className="text-2xl font-extrabold">{err}</h1></div></div>;
    if (!data) return <div className="min-h-screen grid place-items-center text-slate-400">Loading…</div>;

    const a = data.application;
    const c = data.company;
    const primary = c.primary_color;
    const accent = c.accent_color;
    const logoUrl = c.logo_url ? `${API_BASE.replace("/api","")}${c.logo_url}` : "";

    return (
        <div className="min-h-screen bg-slate-50">
            <header className="border-b" style={{ background: primary, color: "white" }}>
                <div className="max-w-3xl mx-auto px-6 py-5 flex items-center gap-4">
                    {logoUrl ? <img src={logoUrl} alt={c.name} className="h-9 max-w-32 object-contain"/> :
                        <div className="font-extrabold text-xl">{c.name}</div>}
                    <div className="ml-auto text-xs uppercase tracking-wider opacity-90 flex items-center gap-1">
                        <ShieldCheck size={14}/> Powered by Fresh Cash Finance
                    </div>
                </div>
            </header>

            <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
                {/* Stepper */}
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
                    {["Apply", "Decision", "Sign", "Done"].map((label, i) => (
                        <div key={label} className="flex items-center gap-2">
                            <div className={`w-7 h-7 rounded-full grid place-items-center text-white ${step > i + 1 ? "bg-green-600" : step === i + 1 ? "" : "bg-slate-300"}`} style={step === i + 1 ? { background: primary } : {}}>
                                {step > i + 1 ? <CheckCircle size={14} weight="fill"/> : i + 1}
                            </div>
                            <span className={step >= i + 1 ? "text-slate-900" : "text-slate-400"}>{label}</span>
                            {i < 3 && <div className="w-8 h-px bg-slate-300"/>}
                        </div>
                    ))}
                </div>

                {/* Amount summary */}
                <div className="bg-white border border-slate-200 rounded-2xl p-5 flex items-center justify-between">
                    <div>
                        <div className="text-xs uppercase tracking-wider text-slate-500">Amount to finance</div>
                        <div className="text-4xl font-extrabold mt-1">{fmt$(a.amount)}</div>
                        <div className="text-xs text-slate-500 mt-1">Requested term: {a.term_months} months</div>
                    </div>
                    <CurrencyDollar size={48} weight="duotone" style={{ color: primary }}/>
                </div>

                {step === 1 && (
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4" data-testid="apply-step-form">
                        <h2 className="font-extrabold text-2xl">Quick application</h2>
                        <p className="text-sm text-slate-500">Soft credit check only — won't affect your credit score.</p>

                        <div className="grid sm:grid-cols-2 gap-3">
                            <Field label="First name" value={form.first_name} onChange={(v) => setForm({ ...form, first_name: v })} testid="apply-first"/>
                            <Field label="Last name" value={form.last_name} onChange={(v) => setForm({ ...form, last_name: v })} testid="apply-last"/>
                            <Field label="Email" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} testid="apply-email"/>
                            <Field label="Phone" type="tel" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} testid="apply-phone"/>
                            <Field label="Date of birth" type="date" value={form.dob} onChange={(v) => setForm({ ...form, dob: v })} testid="apply-dob"/>
                            <Field label="Last 4 of SSN" value={form.ssn4} onChange={(v) => setForm({ ...form, ssn4: v.replace(/\D/g,'').slice(0,4) })} testid="apply-ssn4" maxLength={4}/>
                        </div>

                        <Select label="Estimated credit range" value={form.fico_bucket} onChange={(v) => setForm({ ...form, fico_bucket: v })} testid="apply-fico"
                            options={[
                                ["excellent", "Excellent (740+)"], ["good", "Good (700–739)"],
                                ["fair", "Fair (660–699)"], ["poor", "Poor (620–659)"],
                                ["subprime", "Subprime (<620)"], ["unknown", "I'm not sure"]
                            ]}/>

                        <div className="grid sm:grid-cols-2 gap-3">
                            <Field label="Monthly income ($)" type="number" value={form.monthly_income} onChange={(v) => setForm({ ...form, monthly_income: v })} testid="apply-income"/>
                            <Field label="Monthly debt payments ($)" type="number" value={form.monthly_obligations} onChange={(v) => setForm({ ...form, monthly_obligations: v })} testid="apply-obligations"/>
                        </div>
                        <Select label="Employment" value={form.employment_status} onChange={(v) => setForm({ ...form, employment_status: v })} testid="apply-employment"
                            options={[["full_time","Full-time"],["part_time","Part-time"],["self_employed","Self-employed"],["retired","Retired"],["unemployed","Unemployed"]]}/>

                        <label className="flex items-start gap-2 text-sm">
                            <input type="checkbox" checked={form.consent_soft_pull} onChange={(e) => setForm({ ...form, consent_soft_pull: e.target.checked })} className="mt-1" data-testid="apply-consent"/>
                            <span>I authorize <strong>{c.name}</strong> and Fresh Cash Finance to perform a <strong>soft credit pull</strong> for prequalification. This will <em>not</em> affect my credit score.</span>
                        </label>

                        <button onClick={submit} disabled={submitting || !form.first_name || !form.last_name || !form.consent_soft_pull}
                            className="w-full px-5 py-4 rounded-xl text-white font-bold text-base disabled:opacity-50"
                            style={{ background: primary }}
                            data-testid="apply-submit-btn">
                            {submitting ? "Checking your offer…" : "Check my offer →"}
                        </button>
                    </div>
                )}

                {step === 2 && decision && (
                    <DecisionCard decision={decision} primary={primary} accent={accent} onSignNext={() => setStep(3)} />
                )}

                {step === 3 && decision?.offer && (
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4" data-testid="apply-step-sign">
                        <h2 className="font-extrabold text-2xl">Sign your loan agreement</h2>
                        <OfferTerms offer={decision.offer} />
                        <label className="block">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">Type your full legal name</span>
                            <input type="text" value={signerName} onChange={(e) => setSignerName(e.target.value)}
                                className="mt-1 w-full h-11 px-3 rounded border border-slate-300" data-testid="sign-name"/>
                        </label>
                        <div>
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 block mb-1">Sign below</span>
                            <SignaturePad onChange={setSignatureB64} />
                        </div>
                        <button onClick={sign} disabled={signing || !signerName || !signatureB64}
                            className="w-full px-5 py-4 rounded-xl text-white font-bold text-base disabled:opacity-50"
                            style={{ background: accent }} data-testid="sign-submit-btn">
                            {signing ? "Signing…" : "I agree & sign"}
                        </button>
                    </div>
                )}

                {step === 4 && (
                    <div className="bg-white border-2 border-green-300 rounded-2xl p-8 text-center space-y-3" data-testid="apply-step-done">
                        <CheckCircle size={56} weight="fill" className="mx-auto text-green-600"/>
                        <h2 className="text-3xl font-extrabold">You're all set!</h2>
                        <p className="text-slate-600">Your financing is signed. {c.name} will be in touch to schedule the work and finalize funding.</p>
                        {c.support_phone && <a href={`tel:${c.support_phone}`} className="inline-block px-5 py-3 rounded-xl text-white font-bold" style={{ background: primary }}>Call {c.support_phone}</a>}
                    </div>
                )}

                <div className="text-center text-xs text-slate-400">
                    Fresh Cash Finance · Your information is encrypted and protected.
                </div>
            </main>
        </div>
    );
}

function Field({ label, value, onChange, type = "text", testid, maxLength }) {
    return (
        <label className="block">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">{label}</span>
            <input type={type} value={value} onChange={(e) => onChange(e.target.value)} maxLength={maxLength}
                className="mt-1 w-full h-11 px-3 rounded border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200" data-testid={testid}/>
        </label>
    );
}

function Select({ label, value, onChange, options, testid }) {
    return (
        <label className="block">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600">{label}</span>
            <select value={value} onChange={(e) => onChange(e.target.value)}
                className="mt-1 w-full h-11 px-3 rounded border border-slate-300 text-sm" data-testid={testid}>
                {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
        </label>
    );
}

function OfferTerms({ offer }) {
    return (
        <div className="grid grid-cols-3 gap-3 text-center bg-slate-50 rounded-xl p-4">
            <div><div className="text-2xl font-extrabold">{fmt$(offer.monthly_payment)}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">per month</div></div>
            <div><div className="text-2xl font-extrabold">{offer.apr}%</div><div className="text-[10px] uppercase tracking-wider text-slate-500">APR</div></div>
            <div><div className="text-2xl font-extrabold">{offer.term_months}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">months</div></div>
            <div className="col-span-3 text-xs text-slate-600 border-t border-slate-200 pt-2">
                Amount {fmt$(offer.amount)} · Total finance charge {fmt$(offer.total_finance_charge)}
            </div>
        </div>
    );
}

function DecisionCard({ decision, primary, accent, onSignNext }) {
    if (decision.decision === "declined") {
        return (
            <div className="bg-white border-2 border-rose-200 rounded-2xl p-6 text-center space-y-3" data-testid="apply-step-decline">
                <XCircle size={48} className="mx-auto text-rose-500"/>
                <h2 className="text-2xl font-extrabold">We can't approve this application</h2>
                <p className="text-slate-600 text-sm">Reason: {decision.reason || "credit profile didn't meet criteria"}. You can re-apply after improving your credit or with a co-signer.</p>
            </div>
        );
    }
    if (decision.decision === "manual_review") {
        return (
            <div className="bg-white border-2 border-amber-200 rounded-2xl p-6 text-center space-y-3" data-testid="apply-step-review">
                <Clock size={48} className="mx-auto text-amber-500"/>
                <h2 className="text-2xl font-extrabold">We need a closer look</h2>
                <p className="text-slate-600 text-sm">Your application is being reviewed by a Fresh Cash specialist. You'll hear back within 1 business day.</p>
            </div>
        );
    }
    const isCounter = decision.decision === "counter_offer";
    return (
        <div className="bg-white border-2 border-green-300 rounded-2xl p-6 space-y-4" data-testid={isCounter ? "apply-step-counter" : "apply-step-approved"}>
            <div className="flex items-center gap-2">
                <CheckCircle size={28} weight="fill" className="text-green-600"/>
                <h2 className="text-2xl font-extrabold">
                    {isCounter ? "We've adjusted your offer" : "You're approved!"}
                </h2>
            </div>
            {isCounter && <p className="text-sm text-amber-700 flex items-start gap-1"><Info size={14} className="mt-0.5"/> We extended the term to bring your monthly payment within range.</p>}
            <OfferTerms offer={decision.offer}/>
            <button onClick={onSignNext} className="w-full px-5 py-4 rounded-xl text-white font-bold text-base"
                style={{ background: accent }} data-testid="proceed-sign-btn">
                Accept & sign →
            </button>
        </div>
    );
}
