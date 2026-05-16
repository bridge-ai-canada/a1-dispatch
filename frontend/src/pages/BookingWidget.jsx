import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useEffect } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
import { Wrench, CheckCircle, ArrowRight, CalendarBlank as CalIcon } from "@phosphor-icons/react";
import { Calendar } from "../components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "../components/ui/popover";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const TYPES = ["HVAC", "Plumbing", "Electrical", "Garage Doors", "Roofing", "Appliance Repair", "Other"];

export default function BookingWidget() {
    const { companyId } = useParams();
    const [company, setCompany] = useState(null);
    const [submitted, setSubmitted] = useState(false);
    const [form, setForm] = useState({
        name: "", phone: "", email: "", address: "",
        job_type: "HVAC", description: "", preferred_date: "",
    });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        axios.get(`${API}/public/companies/${companyId}`)
            .then((r) => setCompany(r.data))
            .catch(() => setCompany(false));
    }, [companyId]);

    const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const payload = {
                ...form,
                preferred_date: form.preferred_date ? new Date(form.preferred_date).toISOString() : null,
            };
            await axios.post(`${API}/public/companies/${companyId}/bookings`, payload);
            setSubmitted(true);
        } catch (err) {
            toast.error(err.response?.data?.detail || "Could not submit");
        } finally {
            setLoading(false);
        }
    };

    if (company === false) {
        return <div className="min-h-screen flex items-center justify-center text-slate-500">Company not found.</div>;
    }
    if (!company) {
        return <div className="min-h-screen flex items-center justify-center text-slate-500">Loading...</div>;
    }

    return (
        <div className="min-h-screen bg-slate-50 py-12 px-4">
            <Toaster position="top-right" richColors />
            <div className="max-w-xl mx-auto">
                <div className="text-center mb-8">
                    <div className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.2em] uppercase text-[#1D4ED8]">
                        <Wrench size={14} weight="duotone" /> Book a service
                    </div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-3">{company.name}</h1>
                    <p className="text-slate-500 mt-2">{company.industry} · Request a callback in 2 minutes</p>
                </div>

                {submitted ? (
                    <div className="bg-white border border-slate-200 p-8 text-center" data-testid="booking-success">
                        <CheckCircle size={48} weight="fill" className="text-emerald-500 mx-auto" />
                        <h2 className="font-display text-2xl font-extrabold tracking-tighter mt-4">Request received</h2>
                        <p className="text-slate-600 mt-2">A dispatcher from {company.name} will call you shortly to confirm.</p>
                    </div>
                ) : (
                    <form onSubmit={submit} className="bg-white border border-slate-200 p-6 space-y-4" data-testid="booking-form">
                        <div className="grid sm:grid-cols-2 gap-3">
                            <Field label="Full name" required value={form.name} onChange={update("name")} testid="booking-name" />
                            <Field label="Phone" required value={form.phone} onChange={update("phone")} testid="booking-phone" />
                        </div>
                        <Field label="Email" type="email" value={form.email} onChange={update("email")} testid="booking-email" />
                        <Field label="Service address" required value={form.address} onChange={update("address")} testid="booking-address" />
                        <div className="grid sm:grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-medium">Service type</label>
                                <select value={form.job_type} onChange={update("job_type")} data-testid="booking-type"
                                    className="mt-1 w-full border border-slate-300 px-3 py-2.5 bg-white focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]">
                                    {TYPES.map((t) => <option key={t}>{t}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-medium">Preferred date</label>
                                <Popover>
                                    <PopoverTrigger asChild>
                                        <button type="button" data-testid="booking-date-trigger"
                                            className="mt-1 w-full border border-slate-300 px-3 py-2.5 text-left text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8] bg-white flex items-center gap-2">
                                            <CalIcon size={14} className="text-slate-400" />
                                            {form.preferred_date
                                                ? new Date(form.preferred_date).toLocaleDateString([], { dateStyle: "medium" })
                                                : <span className="text-slate-400">Pick a date</span>}
                                        </button>
                                    </PopoverTrigger>
                                    <PopoverContent className="w-auto p-0" align="start">
                                        <Calendar
                                            mode="single"
                                            selected={form.preferred_date ? new Date(form.preferred_date) : undefined}
                                            onSelect={(d) => setForm((f) => ({ ...f, preferred_date: d ? d.toISOString() : "" }))}
                                            disabled={(d) => d < new Date(new Date().setHours(0,0,0,0))}
                                            initialFocus
                                        />
                                    </PopoverContent>
                                </Popover>
                            </div>
                        </div>
                        <div>
                            <label className="text-xs font-medium">Describe the issue</label>
                            <textarea value={form.description} onChange={update("description")} rows={4}
                                data-testid="booking-description"
                                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                        </div>
                        <button type="submit" disabled={loading} data-testid="booking-submit-button"
                            className="w-full flex items-center justify-center gap-2 bg-[#DC2626] text-white font-semibold py-3 hover:bg-[#B91C1C] disabled:opacity-60">
                            {loading ? "Sending..." : <>Request service <ArrowRight weight="bold" /></>}
                        </button>
                    </form>
                )}

                <div className="mt-8 text-center text-xs text-slate-400">
                    Powered by <Link to="/" className="font-semibold text-slate-600">A1 Field Pro</Link>
                </div>
            </div>
        </div>
    );
}

function Field({ label, testid, ...props }) {
    return (
        <div>
            <label className="text-xs font-medium">{label}{props.required && " *"}</label>
            <input {...props} data-testid={testid}
                className="mt-1 w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
        </div>
    );
}
