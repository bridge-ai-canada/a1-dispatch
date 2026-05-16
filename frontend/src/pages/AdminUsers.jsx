import { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Plus, X, Copy, ShieldCheck, ShieldSlash, Power } from "@phosphor-icons/react";

const ROLE_COLORS = {
    super_admin: "bg-purple-600 text-white",
    owner: "bg-[#DC2626] text-white",
    dispatcher: "bg-[#1D4ED8] text-white",
    office_manager: "bg-indigo-600 text-white",
    csr: "bg-cyan-600 text-white",
    technician: "bg-slate-900 text-white",
    sales_rep: "bg-amber-600 text-white",
    accountant: "bg-emerald-600 text-white",
    customer: "bg-slate-300 text-slate-800",
};

const ROLE_LABEL = {
    super_admin: "Super Admin", owner: "Owner", dispatcher: "Dispatcher",
    office_manager: "Office Mgr", csr: "CSR", technician: "Technician",
    sales_rep: "Sales Rep", accountant: "Accountant", customer: "Customer",
};

export default function AdminUsers() {
    const { user } = useAuth();
    const [users, setUsers] = useState([]);
    const [config, setConfig] = useState(null);
    const [open, setOpen] = useState(false);
    const [invited, setInvited] = useState(null);

    const load = () => api.get("/users").then((r) => setUsers(r.data));
    useEffect(() => {
        load();
        api.get("/config/roles").then((r) => setConfig(r.data));
    }, []);

    const setRole = async (id, role) => {
        try {
            await api.patch(`/users/${id}`, { role });
            toast.success("Role updated");
            load();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    const toggleActive = async (u) => {
        try {
            await api.patch(`/users/${u.id}`, { active: !u.active });
            toast.success(u.active ? "Deactivated" : "Reactivated");
            load();
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        }
    };

    const inviteRoles = config?.invite_allowed?.[user.role] || [];

    return (
        <div data-testid="admin-users-page" className="space-y-6">
            <div className="flex items-end justify-between flex-wrap gap-4">
                <div>
                    <div className="overline">Administration</div>
                    <h1 className="font-display text-4xl font-extrabold tracking-tighter mt-1">User management</h1>
                    <p className="text-sm text-slate-500 mt-2">{users.length} users in your workspace.</p>
                </div>
                {inviteRoles.length > 0 && (
                    <button onClick={() => setOpen(true)} data-testid="open-invite-modal-button"
                        className="bg-[#DC2626] text-white px-5 py-2.5 font-semibold hover:bg-[#B91C1C] flex items-center gap-2">
                        <Plus weight="bold" /> Invite user
                    </button>
                )}
            </div>

            <div className="border border-slate-200 overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr className="text-left">
                            <th className="px-4 py-3 font-semibold">Name</th>
                            <th className="px-4 py-3 font-semibold">Email</th>
                            <th className="px-4 py-3 font-semibold">Role</th>
                            <th className="px-4 py-3 font-semibold">MFA</th>
                            <th className="px-4 py-3 font-semibold">Status</th>
                            <th className="px-4 py-3 font-semibold text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {users.map((u) => (
                            <tr key={u.id} className={`hover:bg-slate-50 ${u.active === false ? "opacity-50" : ""}`}>
                                <td className="px-4 py-3 font-medium" data-testid={`user-row-${u.id}`}>{u.name}</td>
                                <td className="px-4 py-3 text-slate-600">{u.email}</td>
                                <td className="px-4 py-3">
                                    {u.role === "owner" || u.role === "super_admin" || u.id === user.id ? (
                                        <span className={`text-[10px] px-2 py-0.5 font-semibold uppercase tracking-wider ${ROLE_COLORS[u.role]}`}>{ROLE_LABEL[u.role]}</span>
                                    ) : (
                                        <select value={u.role} onChange={(e) => setRole(u.id, e.target.value)}
                                            data-testid={`role-select-${u.id}`}
                                            className="text-xs border border-slate-300 px-2 py-1 bg-white">
                                            {config?.roles.filter((r) => r !== "owner" && r !== "super_admin").map((r) => (
                                                <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                                            ))}
                                        </select>
                                    )}
                                </td>
                                <td className="px-4 py-3">
                                    {u.mfa_enabled
                                        ? <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><ShieldCheck size={14} weight="fill" /> Enabled</span>
                                        : <span className="inline-flex items-center gap-1 text-xs text-slate-400"><ShieldSlash size={14} /> Off</span>}
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`text-xs font-medium ${u.active === false ? "text-[#DC2626]" : "text-emerald-700"}`}>
                                        {u.active === false ? "Deactivated" : "Active"}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-right">
                                    {u.role !== "owner" && u.id !== user.id && (
                                        <button onClick={() => toggleActive(u)} data-testid={`toggle-active-${u.id}`}
                                            className="text-xs px-2 py-1 border border-slate-300 hover:bg-slate-50 inline-flex items-center gap-1">
                                            <Power size={12} /> {u.active === false ? "Reactivate" : "Deactivate"}
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {open && (
                <InviteModal
                    roles={inviteRoles}
                    onClose={() => setOpen(false)}
                    onInvited={(data) => { setOpen(false); setInvited(data); load(); }}
                />
            )}

            {invited && <InvitedModal data={invited} onClose={() => setInvited(null)} />}
        </div>
    );
}

function InviteModal({ roles, onClose, onInvited }) {
    const [form, setForm] = useState({ name: "", email: "", role: roles[0] || "csr" });
    const [saving, setSaving] = useState(false);
    const submit = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const { data } = await api.post("/users/invite", form);
            onInvited(data);
        } catch (err) {
            toast.error(formatApiError(err.response?.data?.detail));
        } finally { setSaving(false); }
    };
    return (
        <Modal title="Invite user" onClose={onClose}>
            <form onSubmit={submit} className="p-6 space-y-3">
                <input required placeholder="Full name" value={form.name} onChange={(e) => setForm({...form, name: e.target.value})}
                    data-testid="invite-name-input"
                    className="w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                <input required type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({...form, email: e.target.value})}
                    data-testid="invite-email-input"
                    className="w-full border border-slate-300 px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]" />
                <select value={form.role} onChange={(e) => setForm({...form, role: e.target.value})}
                    data-testid="invite-role-select"
                    className="w-full border border-slate-300 px-3 py-2.5 bg-white">
                    {roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                </select>
                <button type="submit" disabled={saving} data-testid="invite-submit-button"
                    className="w-full bg-[#1D4ED8] text-white font-semibold py-2.5 hover:bg-[#1E40AF] disabled:opacity-60">
                    {saving ? "Sending..." : "Send invite"}
                </button>
            </form>
        </Modal>
    );
}

function InvitedModal({ data, onClose }) {
    const copy = (txt, label) => { navigator.clipboard.writeText(txt); toast.success(`${label} copied`); };
    return (
        <Modal title="Invite sent" onClose={onClose}>
            <div className="p-6 space-y-4" data-testid="invited-modal">
                <p className="text-sm text-slate-600">
                    {data.email_sent
                        ? <>Email sent to <strong>{data.email}</strong>. They can also use this direct link:</>
                        : <>Share this link with <strong>{data.email}</strong> to set their password:</>}
                </p>
                <div className="space-y-1">
                    <div className="overline">Setup link</div>
                    <div className="flex items-center gap-1">
                        <input readOnly value={data.setup_url} data-testid="invited-setup-link"
                            className="flex-1 border border-slate-300 px-2 py-2 font-mono text-xs bg-slate-50" />
                        <button onClick={() => copy(data.setup_url, "Link")}
                            className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><Copy size={14} /></button>
                    </div>
                </div>
                <div className="space-y-1">
                    <div className="overline">Temporary password</div>
                    <div className="flex items-center gap-1">
                        <input readOnly value={data.temp_password}
                            className="flex-1 border border-slate-300 px-2 py-2 font-mono text-xs bg-slate-50" />
                        <button onClick={() => copy(data.temp_password, "Password")}
                            className="h-9 w-9 border border-slate-300 hover:bg-slate-50 flex items-center justify-center"><Copy size={14} /></button>
                    </div>
                </div>
                <button onClick={onClose} className="w-full bg-slate-900 text-white py-2.5 font-semibold hover:bg-slate-800">Done</button>
            </div>
        </Modal>
    );
}

function Modal({ title, onClose, children }) {
    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white w-full max-w-md border border-slate-300" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                    <h2 className="font-display text-2xl font-extrabold tracking-tighter">{title}</h2>
                    <button onClick={onClose} data-testid="modal-close-button"><X size={20} /></button>
                </div>
                {children}
            </div>
        </div>
    );
}
