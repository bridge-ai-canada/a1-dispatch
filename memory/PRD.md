# A1 Field Pro — Product Requirements Document

## Original problem statement
Create a production-ready SaaS field service management platform called "A1 Field Pro",
owned by A1 HVAC N DE-GO. Inspired by Workiz workflow but original with better UI/UX,
stronger automation, and full white-label capability.

Target industries: HVAC, Plumbing, Electrical, Appliance Repair, Garage Doors, Roofing,
Home Services. Multi-tenant SaaS architecture, modern, fast, mobile-first, dark-mode
capable, cleaner than Workiz, simpler than ServiceTitan.

## Adapted tech stack (per platform constraints)
- Frontend: React 19 + Tailwind + Shadcn UI + Phosphor Icons
- Backend: FastAPI + Motor (MongoDB async)
- Database: MongoDB (multi-tenant via `company_id` scoping)
- Auth: JWT in httpOnly cookies (bcrypt password hashing)
- Payments: Stripe Checkout via `emergentintegrations`

## User personas
- **Owner** — full access, billing, team, settings, all jobs.
- **Dispatcher** — creates and assigns work orders, schedules technicians.
- **Technician** — mobile-friendly "My Jobs" view: today's route, status updates, payment capture.

## Core requirements (static)
1. Multi-tenant: every record scoped by `company_id` from JWT.
2. Role-based access: owner / dispatcher / technician.
3. JWT in httpOnly cookies; FastAPI `withCredentials` on all axios calls.
4. CORS limited to frontend origin with credentials.
5. Stripe Checkout for per-job invoices.
6. Mobile-first technician view.
7. Red / Blue / White brand palette, Swiss high-contrast design.

## What's been implemented (Feb 2026 — v1)
- **Auth**: register (creates company + owner), login, logout, /me. Bcrypt + JWT cookies.
- **Companies & Team**: company seeded on signup; invite dispatchers / technicians; delete members.
- **Customers CRM**: list + create.
- **Jobs / Work Orders**: create, edit, delete, filter by status, assign technician, schedule, price.
- **Dashboard**: KPIs, pipeline funnel, recent jobs.
- **Schedule**: Week-view grid; jobs placed by `scheduled_at` & assignee.
- **Technician Mobile View**: Today/Upcoming/Completed, status-advance, one-tap charge.
- **Stripe Payments**: per-job checkout, polling status, auto job→completed+paid.
- **Marketing landing page**.
- **Demo seed**: 1 company, 3 users, 4 sample jobs.

## What's been implemented (Phase 1 — Feb 2026 — v1.1)
- **Job detail page** (`/app/jobs/:id`): editable notes, photo upload/grid/delete via Emergent object storage, customer signature pad (canvas → base64 PNG), inline status advance + Stripe charge.
- **Drag-and-drop schedule**: unscheduled sidebar; drag job onto day/hour cell → PATCH scheduled_at; auto-promotes status.
- **Public booking widget** (`/book/:companyId`): no-auth customer form → creates an unscheduled job tagged `source=booking_widget`; shareable link with Copy button in Settings.
- **Multi-tenant file isolation**: `/api/files/{path:path}` validates path prefix against JWT company_id.

Testing: backend 30/30 pytest pass (18 baseline + 12 phase 1); frontend critical flows verified.

## What's been implemented (Phase 2A — Feb 2026 — v1.2)
- **White-label branding**: owner-only `PATCH /api/companies/me` for primary + accent color; `POST /api/companies/me/logo` (multipart) stores logo via object storage and writes `company.branding.logo_path`. Settings UI: logo uploader, 5 color presets, primary/accent color pickers, Save button.
- **PDF Invoice**: `GET /api/jobs/{id}/invoice.pdf` generates a branded invoice (header bar in company primary color, total in accent, PAID stamp when paid) via reportlab. "Invoice PDF" button on JobDetail opens it in a new tab using same-origin httpOnly cookie auth.
- **Booking widget polish**: shadcn Calendar inside Popover replaces the native datetime picker for the "Preferred date" field; Settings page now exposes a copy-paste `<iframe>` embed snippet alongside the direct link.

Testing: backend 40/40 pytest pass (30 prior + 10 new); frontend critical flows verified.

## What's been implemented (Phase 2B — Feb 2026 — v1.3)
- **9 roles + permissions matrix**: `super_admin`, `owner`, `dispatcher`, `office_manager`, `csr`, `technician`, `sales_rep`, `accountant`, `customer`. Permissions checked via `require_perm()`; invitation rights via `INVITE_ALLOWED`. Role escalation guarded (owner cannot promote to `super_admin` or `owner`).
- **Super admin bootstrap**: seeded from `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` env on startup; no `company_id`; `?all_tenants=true` returns cross-tenant lists.
- **TOTP MFA (required for all)**: `/api/auth/mfa/setup` returns QR + base32 secret; `/enable` & `/disable` (password-protected). `Protected` layout redirects `/app/*` to `/setup-mfa` if not enrolled. Login is two-step — backend returns `detail:"mfa_required"` triggers frontend code prompt.
- **Password reset**: `/api/auth/forgot` returns 200 always; emails reset link via Resend; also returns `reset_url` so owners can copy if email isn't delivered. `/api/auth/reset` updates password and revokes all sessions.
- **Sessions**: stored on every login with UA/IP; `GET /api/sessions` marks the current; `DELETE /api/sessions/{id}` revokes; revoked sessions block subsequent requests via JWT `sid` claim. Settings → Active Sessions UI.
- **Activity log**: events auto-emitted on login, invite, role/active changes, MFA on/off, company creation, jobs (planned). RBAC via `activity.read` perm. New `/app/admin/activity` page with action chips.
- **Admin User Management**: `/app/admin/users` table (name, email, role dropdown, MFA badge, active toggle, deactivate), Invite modal with role selector limited by `INVITE_ALLOWED`, post-invite modal with copy buttons for setup link + temp password. `POST /api/users/invite` sends Resend email and falls back to in-app link reveal.
- **Resend email**: branded HTML template (`email_layout`) for invites + password reset.

Testing: backend 63/63 pytest pass (40 prior + 23 new); frontend critical flows verified; 0 critical defects (1 minor ObjectId fix + 1 privilege-escalation guard added).

## Backlog (prioritized)
### P0 — Phase 2C (next)
- Email verification on signup (Resend, optional gate before invoicing)
- Emergent-managed Google login
- Apple login (needs Apple Developer account from user)
- Render uploaded company logo on landing/booking widget headers (saved but not yet displayed)
- Apply company.branding.primary_color to booking widget header + submit button

### P1 — Soon
- Customer/Homeowner self-service portal (role exists, no UI yet)
- Job activity events (jobs.created, jobs.completed, payment.received) into activity log
- Hex color regex validation, password strength rules (uppercase + digit + length≥8)
- Resend email delivery status surfaced in activity log
- **Refactor**: split `server.py` (~1300 lines) into `routers/{auth,mfa,sessions,activity,admin,jobs,companies,files,public,payments,invoice}.py`

### P2 — Future
- Route optimization
- SMS notifications (Twilio)
- Recurring jobs / maintenance plans
- Reports / analytics export
- Mobile native app (React Native)

## Demo credentials
Owner: `demo@a1fieldpro.com` / `Demo1234!`
Dispatcher: `dispatcher@a1fieldpro.com` / `Demo1234!`
Technician: `tech@a1fieldpro.com` / `Demo1234!`
