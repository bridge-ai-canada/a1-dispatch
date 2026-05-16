"""Roles, permissions matrix and helpers for A1 Field Pro."""

ROLES = [
    "super_admin", "owner", "dispatcher", "office_manager",
    "csr", "technician", "sales_rep", "accountant", "customer",
]

ROLE_LABELS = {
    "super_admin": "Super Admin",
    "owner": "Company Owner",
    "dispatcher": "Dispatcher",
    "office_manager": "Office Manager",
    "csr": "CSR",
    "technician": "Technician",
    "sales_rep": "Sales Rep",
    "accountant": "Accountant",
    "customer": "Customer",
}

# Permissions: "*" = all; "<resource>.*" = all on resource; otherwise exact.
PERMISSIONS = {
    "super_admin":    ["*"],
    "owner":          ["*"],
    "dispatcher":     ["jobs.*", "schedule.*", "team.read", "customers.*", "activity.read"],
    "office_manager": ["jobs.*", "customers.*", "team.read", "team.invite", "payments.read", "invoice.*", "activity.read"],
    "csr":            ["jobs.create", "jobs.read", "jobs.update", "customers.*"],
    "technician":     ["jobs.read", "jobs.update_status", "jobs.photos", "jobs.signature"],
    "sales_rep":      ["customers.*", "jobs.create", "jobs.read"],
    "accountant":     ["jobs.read", "payments.*", "invoice.*", "activity.read"],
    "customer":       ["self.read"],
}

# Which roles a given role is allowed to invite.
INVITE_ALLOWED = {
    "super_admin": set(ROLES),
    "owner":       {"dispatcher","office_manager","csr","technician","sales_rep","accountant"},
    "office_manager": {"csr","technician","sales_rep","dispatcher"},
}


def has_perm(role: str, perm: str) -> bool:
    grants = PERMISSIONS.get(role, [])
    if "*" in grants:
        return True
    for g in grants:
        if g == perm:
            return True
        if g.endswith(".*") and perm.startswith(g[:-1]):
            return True
    return False
