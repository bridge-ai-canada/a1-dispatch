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

## What's been implemented (Phase 2C — Feb 2026 — v1.4)
- **Email verification**: register sends Resend verification email best-effort; `POST /api/auth/verify?token=...`; `POST /api/auth/verify/resend`; non-blocking amber banner in app shell prompts unverified users.
- **Emergent Google login**: "Continue with Google" buttons on `/login` + `/register`; `AuthCallback` page processes `#session_id=...` synchronously (race-condition-safe); backend `/api/auth/google/exchange` calls Emergent's session-data endpoint, links existing users by email, creates new users as `customer` role (`company_id=null`) for homeowners.
- **Customer self-service portal** (`/portal`): no-auth landing card → Continue with Google; auth'd portal lists Upcoming / Pending / Past visits scoped by `customer_email==user.email` across all tenants; PDF invoice link on past visits; quick-book buttons for any company they've worked with.
- **Branded booking widget**: `/book/:companyId` reads `company.branding` and applies `primary_color` to header overline + `accent_color` to submit button; renders uploaded `logo_path` if present.
- **Job model extended** with `customer_email` so portal scoping works; public booking persists it.

Testing: backend **77/77** pytest pass (14 new + 63 prior); frontend critical flows verified; 0 defects.

## What's been implemented (Polish — Feb 2026 — v1.5)
- **Official logo** uploaded by owner (A1 Field Pro on dark navy with HVAC mark) is now used as the default everywhere via the `Brand` component; `BookingWidget` falls back to this logo when a tenant has no custom branding logo.
- **Brand component is auth-aware**: when a user is logged in and their company has a `branding.logo_path`, the layout/landing nav automatically renders the company logo instead of the A1 default — true white-label across the app for staff users.
- **Database indexes** added on `jobs.customer_email` (portal scaling), `activity.(company_id, created_at)`, `sessions.user_id` for query performance at scale.

## What's been implemented (Polish + Maintenance — Feb 2026 — v1.8)
- **Invite verify-email gate**: `POST /api/users/invite` now 403s with friendly detail when the actor's `email_verified=False`. Demo owner remains verified.
- **Recurring jobs / maintenance plans**:
  - New `recurring_jobs` collection + 8 endpoints (list, create, patch, delete, force-run).
  - Cadences: `weekly` (7d), `biweekly` (14d), `monthly` (30d), `quarterly` (90d), `annually` (365d), `custom` (`interval_days` required).
  - Lazy materialization on `GET /api/recurring-jobs` AND `GET /api/jobs` — due plans auto-create real `jobs` with `source='recurring'` and `recurring_id` linkback.
  - Activity events: `recurring.created`, `recurring.deleted`, `recurring.materialized`.
  - Frontend: new `/app/recurring` page with table view, create form (6 cadence options + custom day input), pause/resume, force-run, delete.
- **Analytics CSV exports**:
  - `GET /api/exports/jobs.csv`, `customers.csv`, `payments.csv` with `?from=YYYY-MM-DD&to=YYYY-MM-DDT23:59:59` date filters.
  - Owner/accountant/super_admin only (403 for everyone else).
  - Frontend: new `/app/reports` page with date pickers + three download cards.
- **Route optimization**:
  - `POST /api/jobs/optimize-route` body `{technician_id, date, gap_min=30, dry_run=false}`.
  - Heuristic: groups by ZIP (5-digit from end of address), then street-number ascending, then re-spaces `scheduled_at` from earliest current time, advancing by `duration + gap_min`.
  - Owner/dispatcher/office_manager only.
  - Activity: `route.optimized`.
  - Frontend: "Optimize tech…" dropdown + "Optimize today" button in Schedule header.

Testing: 146 baseline + 35 new = **181/181 backend tests green**, 0 critical issues.

## What's been implemented (Push expansion + UX polish — Feb 2026 — v1.11)
- **New work order time fields**: The job modal now has both **Scheduled** start AND **Ends** datetime pickers alongside Duration and Price. Changing either time auto-recomputes duration; changing duration auto-extends the end picker. Form remains backwards-compatible — backend still stores `scheduled_at + duration_min` only.
- **Push notifications for 3 additional events**:
  - **`payment.received`** — pushes to job creator (or fallback to assigned tech) on both Stripe poll and webhook flows. `"Payment received · $X.XX for <job>"`.
  - **`tip.received`** — pushes to assigned tech (or fallback to creator) on both portal poll and webhook flows. `"Tip received · $X.XX from <customer>"`.
  - **`rating.created`** — pushes to assigned tech with star count + customer name. **Extra: low-rating alerts** (1–2 stars) also push to the company owner under a separate `low-rate-{job_id}` tag.
  - **`recurring.materialized`** — pushes to the assigned tech of newly auto-created occurrences (both lazy `_materialize_due` and force `/run` paths).
- **Robust projections**: Removed `_id:0` from inclusion-only Mongo projections to avoid Motor-version fragility (critical action item from testing agent).
- **Native React Native scaffolding** (`/app/mobile/`): Expo SDK 51 + Expo Router + TypeScript app with login screen, today/all/profile tabs, job detail with Start/Complete/Charge buttons + tap-to-call/map. Source-code only — build & run locally with `npx expo start`. Same `/api/*` endpoints as web. Wire it up in 5 minutes on a Mac.

Testing: 207 baseline + 15 new push hooks = **222/222 backend tests green**, 0 critical issues. Mobile app: `tsc --noEmit` clean.

## What's been implemented (Web-Push pipeline — Feb 2026 — v1.10)
- **VAPID keys** auto-generated and persisted to `backend/.env` (`VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT`).
- **Backend push service** (`push_service.py`): `send_push_to_user(user_id, payload)` sends to every active subscription for the user via `pywebpush`. Subscriptions that return 404/410 are automatically removed.
- **Push router** (`/api/push/*`):
  - `GET /push/public-key` — public, returns the VAPID public key for the frontend `applicationServerKey`.
  - `POST /push/subscribe` — upsert a subscription by endpoint. Updates keys + user_id on re-subscribe.
  - `DELETE /push/subscribe?endpoint=…` — remove the actor's subscription.
  - `GET /push/subscriptions/me` — list (without raw keys) for diagnostics.
  - `POST /push/test` — fire a test notification. Cross-tenant + cross-role guarded.
- **Send-on-event hooks**:
  - `POST /api/jobs` with `assigned_to ≠ self` → push to assigned tech: "New job assigned" + scheduled time + tap-through URL.
  - `PATCH /api/jobs/{id}` with a new `assigned_to` → "New job assigned" push; with a `scheduled_at` change → "Job rescheduled" push to current tech.
  - All push sends wrapped in try/except so job CRUD never breaks if push delivery fails.
- **Frontend opt-in**: `PushOptIn` component on `/app/my-jobs` with 3-state UI (default/granted/denied), enable/disable buttons, and a "Test" button that calls `/api/push/test`. `push.js` helper handles `Notification.requestPermission` + `PushManager.subscribe` + base64url ↔ Uint8Array conversion.
- **Service worker** (`sw.js`) already handles `push` + `notificationclick` events from v1.9.

Testing: 181 baseline + 26 new = **207/207 backend tests green**, 0 critical issues.

## What's been implemented (PWA — Feb 2026 — v1.9)
- **Progressive Web App**: A1 Field Pro is now installable on iOS & Android home screens.
  - `/public/manifest.json` — standalone display, brand colors, A1 logo as icon (192/512), shortcuts to Today's Jobs + Schedule.
  - `/public/sw.js` — install/activate/fetch handlers. Strategy: network-first for `/api/*` (with stale-cache fallback when offline), cache-first for static assets, network-first with `/offline.html` fallback for navigations. Auth & payment endpoints intentionally bypass cache.
  - `/public/offline.html` — branded offline page (red OFFLINE badge, "Try again" button).
  - PWA meta tags in `index.html` (theme-color, apple-touch-icon, apple-mobile-web-app-capable, viewport-fit=cover).
  - `src/lib/pwa.js` — service-worker registration + `beforeinstallprompt` brokering.
  - `src/components/InstallPrompt.jsx` — install banner/card with iOS "Add to Home Screen" walkthrough modal (3-step guide). Auto-hides when already installed or dismissed; LocalStorage-persisted dismissal.
  - `src/components/OfflineIndicator.jsx` — red top-bar strip when `navigator.onLine === false`.
  - Web-push scaffolding in `sw.js` (push + notificationclick handlers) ready for future Twilio/Web-Push backend integration.
- **Result**: Technicians on real iOS Safari can tap Share → Add to Home Screen and launch A1 Field Pro fullscreen. Android Chrome shows the native install banner. SW caches the latest `/api/jobs` response so off-grid techs still see their day's route.

## What's been implemented (Refactor + Polish — Feb 2026 — v1.7)
- **Backend refactor**: `server.py` cut from ~1,400 → 175 lines. Routes now split across `/app/backend/routers/` modules: `auth.py`, `admin.py`, `companies.py`, `customers.py`, `jobs.py`, `payments.py`, `public_routes.py`, `portal.py`. Shared infra remains in `deps.py`. Mounted via single `APIRouter(prefix="/api")` in `server.py`. **120/120 tests still pass** (no behavior change).
- **Industry icon palette** on `BookingWidget` when a company hasn't uploaded a logo: per-industry phosphor icon (Snowflake/Drop/Lightning/Garage/House/Plug/Wrench) on a rounded tile tinted with `branding.primary_color`. Contrast-aware foreground (white on dark, ink on light).
- **Customer portal — rate technician + tip**:
  - `POST /api/portal/jobs/{job_id}/rate` body `{rating:1-5, comment?}` → persists `rating`, `rating_comment`, `rated_at`, `rated_by` on the job; logs `rating.created` activity. Customer-only, completed-jobs only.
  - `POST /api/portal/jobs/{job_id}/tip-checkout` body `{amount, origin_url}` → Stripe checkout URL with `metadata.type='tip'`; inserts `payment_transactions` doc with `type:'tip'`.
  - `GET /api/portal/payments/status/{session_id}` → customer-side polling that credits `jobs.tip += amount` and emits `tip.received` on transition to paid.
  - Stripe webhook also handles `type='tip'` transactions (increments `jobs.tip` instead of marking job paid; emits `tip.received`).
  - Frontend `RateAndTip` component on every completed past visit: 5-star picker + optional comment + 4 tip presets ($5/$10/$20/$40) + custom amount. After Stripe redirect, portal polls `/portal/payments/status/{sid}` for up to 6 retries and toasts "Thanks for the tip!".
- **Resend email delivery status in activity log**: `send_email()` accepts optional `actor` + `purpose`; logs `email.sent` activity with meta `{to, subject, purpose, status, email_id?, error?}`. Statuses: `sent`, `failed`, `skipped`, `no_id`. Hooked into auth.forgot, auth.verify_resend, admin.invite_user.

## What's been implemented (Polish — Feb 2026 — v1.6)
- **Job lifecycle activity events**: `jobs.created` (on POST /jobs) and `jobs.{scheduled|in_progress|completed|cancelled}` (on PATCH /jobs/{id}) now flow into the activity feed with `{title, status}` meta.
- **payment.received activity event**: emitted by both the polling endpoint (`GET /payments/status/{session_id}`) and Stripe webhook when a transaction transitions to paid, with `{amount, currency, session_id}` meta.
- **Verify-email gate before payment-link send**: `POST /api/payments/checkout` now returns 403 with a friendly "Verify your email before sending payment links…" detail when the staff user has `email_verified=False`. Demo seed users have `email_verified=True` so the existing flow continues to work.
- **Booking widget returns full job**: `POST /api/public/companies/{company_id}/bookings` now responds `{ok, job_id, company_name, job:{…full document…}}` so the booking widget UI can show a confirmation card without a second round-trip.
- **Hex color regex** on BrandingIn: `^#[0-9A-Fa-f]{6}$` enforced for `primary_color` / `accent_color` (Pydantic 422 on bad input).
- **Password strength rules** on RegisterIn + ResetIn: min 8 chars, must include at least one letter and one number (Pydantic 422 on weak input).

Testing: backend regression + 26 new targeted cases — 115 pass / 0 critical issues. Stale `test_a1fieldpro` + `test_phase_crm` assertions updated for paginated customers and full claude model id.

## Backlog (prioritized)
### P0 — Done in v1.7
- ✅ `server.py` refactor split into routers/

### P1 — Done in v1.8
- ✅ Invite verify-email gate
- ✅ Recurring jobs / maintenance plans
- ✅ Analytics CSV exports
- ✅ Route optimization (ZIP-based heuristic)

### v1.9 — Done
- ✅ PWA (installable, offline-capable, push-ready)

### v1.10 — Done
- ✅ Backend Web-Push trigger pipeline (VAPID, subscription endpoint, send-on-event hooks)

### v1.11 — Done
- ✅ Push notifications for 3 additional events (payment.received, tip.received, rating.created with low-rating owner alert, recurring.materialized)
- ✅ Work order start + end time fields in new-job modal
- ✅ Native React Native scaffolding (`/app/mobile/` — Expo SDK 51, source-code only)

### P1 — Remaining
- Apple login (needs Apple Developer credentials from user)

### P2 — Future
- Android login (needs Google Play Developer credentials)
- Real geocoding for route optimization (Google Maps / Mapbox API)
- SMS notifications (Twilio — needs credentials)
- Booking-confirmation email back to customers
- Mobile app push (Expo Notifications) — adapter from VAPID web push to FCM/APNs tokens
- Mobile app: photo upload (`expo-image-picker`), signature capture, offline queue

## Demo credentials
Owner: `demo@a1fieldpro.com` / `Demo1234!`
Dispatcher: `dispatcher@a1fieldpro.com` / `Demo1234!`
Technician: `tech@a1fieldpro.com` / `Demo1234!`
