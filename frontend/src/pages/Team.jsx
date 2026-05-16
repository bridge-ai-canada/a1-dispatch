import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { Plus, X, Trash } from "@phosphor-icons/react";

const ROLE_COLORS = {
    owner: "bg-[#DC2626] text-white",
    dispatcher: "bg-[#1D4ED8] text-white",
    technician: "bg-slate-900 text-white",
};

export default function Team() {
    const { user } = useAuth();
    const [team, setTeam] = useState([]);
    const [open, setOpen] = useState(false);

    const load = () => api.get("/team").then((r) => setTeam(r.data));
    useEffect(() => { load(); }, []);

    const remove = async (id) => {
        if (!window.confirm("Remove this team member?")) return;
        try {
            await api.delete(`/team/${id}`);
            toast.success("Member removed");
            load();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    return (
        <div data-testid="team-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">People</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">Team</h1>
                </div>
                <button onClick={() => setOpen(true)} data-testid="add-team-button"
                    className="bg-[#DC2626] text-white px-5 py-2.5 font-semibold hover:bg-[#B91C1C] flex items-center gap-2">
                    <Plus weight="bold" /> Invite member
                </button>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-slate-200 border border-slate-200">
                {team.map((m) => (
                    <div key={m.id} className="bg-white p-5" data-testid={`team-card-${m.id}`}>
                        <div className="flex items-start justify-between">
                            <div className="h-10 w-10 bg-slate-900 text-white font-display font-extrabold text-lg flex items-center justify-center">
                                {m.name.charAt(0)}
                            </div>
                            <span className={`text-[10px] px-2 py-0.5 font-semibold tracking-wider uppercase ${ROLE_COLORS[m.role] || "bg-slate-200"}`}>{m.role}</span>
                        </div>
                        <div className="mt-4 font-semibold">{m.name}</div>
                        <div className="text-sm text-slate-500 truncate">{m.email}</div>
                        {user.role === "owner" && m.id !== user.id && (
                            <button
                                onClick={() => remove(m.id)}
                                data-testid={`remove-team-${m.id}`}
                                className="mt-4 text-xs flex items-center gap-1 text-[#DC2626] hover:underline">
                                <Trash size={12} /> Remove
                            </button>
                        )}
                    </div>
                ))}
            </div>

            {open && <InviteModal onClose={() => setOpen(false)} onSaved={() => { setOpen(false); load(); }} />}
        </div>
    );
}

function InviteModal({ onClose, onSaved }) {
    const [form, setForm] = useState({ name: "", email: "", password: "", role: "technician" });
    const [saving, setSaving] = useState(false);
    const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            await api.post("/team", form);
            toast.success("Member added");
            onSaved();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        } finally { setSaving(false); }
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-md border border-slate-300" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                    <h2 className="font-display text-2xl font-extrabold tracking-tighter">Invite Member</h2>
                    <button onClick={onClose}><X size={20} /></button>
                </div>
                <form onSubmit={submit} className="p-6 space-y-4">
                    <input required placeholder="Full name" value={form.name} onChange={update("name")} data-testid="invite-name-input"
                        className="w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    <input required type="email" placeholder="Email" value={form.email} onChange={update("email")} data-testid="invite-email-input"
                        className="w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    <input required type="password" placeholder="Temp password" value={form.password} onChange={update("password")} data-testid="invite-password-input"
                        className="w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                    <select value={form.role} onChange={update("role")} className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                        <option value="technician">Technician</option>
                        <option value="dispatcher">Dispatcher</option>
                    </select>
                    <button type="submit" disabled={saving} data-testid="invite-submit-button"
                        className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                        {saving ? "Adding..." : "Add member"}
                    </button>
                </form>
            </div>
        </div>
    );
}
