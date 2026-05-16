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
- **Dashboard**: KPIs (jobs today, revenue today, active technicians, completion rate), pipeline funnel, recent jobs.
- **Schedule**: Week-view grid with hour rows + day columns; jobs placed by `scheduled_at` & assignee.
- **Technician Mobile View** (`/app/my-jobs`): Today / Upcoming / Completed sections, status-advance buttons, one-tap charge.
- **Stripe Payments**: `/api/payments/checkout` per job, polling-based status verification on success page, transactions persisted, automatic job → completed + paid.
- **Marketing landing page**: hero, industries strip, features grid, mobile showcase, CTA.
- **Demo seed**: A1 HVAC N DE-GO company, 3 users (owner/dispatcher/tech), 4 sample jobs.

Testing: backend 18/18 pytest pass; frontend critical flows verified via Playwright.

## Backlog (prioritized)
### P0 — Next session
- Drag-and-drop on Schedule (currently view-only)
- Job detail page (notes, photos, signature)
- Real invoices PDF + email send

### P1 — Soon
- White-label settings (logo, primary color upload)
- Google / Apple social login
- MFA (TOTP)
- Customer-facing booking widget

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
