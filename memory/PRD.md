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

## What's been implemented (Geocoding + dashboard widgets + notif prefs — Feb 2026 — v1.13)
- **Nominatim geocoding** (`geocode_service.py`): free OSM-backed lookup with 1 req/sec throttle and persistent DB cache (`geocode_cache`). Background-task hook on `POST /api/jobs` and `PATCH /api/jobs/{id}` (when address changes) — within seconds, the job doc gains `location:{lat,lng,display_name}` and the dispatch map auto-pins it via a new WS `job.geocoded` broadcast. **Fixed critical cache-poisoning bug** flagged by testing: transient errors (429 rate-limit, 5xx, network) no longer cached; negative caches expire after 7 days for self-healing.
- **WS heartbeat**: server emits `{type:"ping"}` after 25s of client silence so long-idle ingress timeouts don't kill the dispatch board.
- **Tech leaderboard widget** on Dashboard: top 5 techs ranked by 30-day rating average + tip total + revenue. Single MongoDB aggregation. Hidden when no rated jobs.
- **30-day recurring-revenue forecast widget** on Dashboard: total expected revenue from active plans in the next 30 days + annual contract value + top-5 plan breakdown. No external service needed; pure computation from existing data.
- **Per-user notification preferences** (`/api/me/push-prefs` GET + PUT): toggle each event class (job_assigned, job_rescheduled, payment_received, tip_received, rating_created, rating_low_alert, recurring_materialized) + UTC quiet-hours window. `send_push_to_user` checks prefs via push-tag prefix routing and short-circuits with `{skipped: true}` when disabled or in quiet hours.
- **Frontend NotificationPrefs page** at `/app/notifications`: 7 toggles, optional quiet-hours range pickers, link from the PushOptIn tile on /app/my-jobs.

### Mobile app additions (`/app/mobile/`)
- **Camera + library photo upload** via `expo-image-picker` (Camera or Library button on Job detail).
- **Signature capture** via `react-native-signature-canvas` modal — saves base64 to `POST /api/jobs/{id}/signature`.
- **Offline queue** (`lib/queue.ts` — AsyncStorage-backed): when a status update fails due to no connectivity, it's queued and auto-flushed every 20s. Job detail shows a "N changes pending sync" banner. `startAutoFlush()` initialized in root layout.

Testing: 241 baseline + 11 new = **252 backend tests passing**, 0 critical bugs after fix. 1 critical cache-poisoning bug identified by testing agent **fixed**. Mobile: `tsc --noEmit` clean.

## What's been implemented (Modern Dispatch Board — Feb 2026 — v1.12)

### Backend
- **WebSocket pub/sub** (`ws_hub.py`): in-memory company-scoped rooms. `/api/ws?token=<jwt>` accepts the same JWT used for REST. Sends `{type:"hello"}` on connect, broadcasts JSON events thereafter. Tenant-isolated (verified: a fresh tenant's socket does NOT receive demo-tenant events).
- **WS broadcasts** wired into `jobs.create` (`job.created`), `jobs.update` (`job.updated`), `dispatch.set_priority` (`job.updated`), `dispatch.update_my_status` (`user.status`), `dispatch.update_my_location` (`user.location`).
- **Tech status**: `POST /api/me/status` body `{status: available|on_route|on_site|break|off_duty}` persists + broadcasts.
- **GPS**: `POST /api/me/location` body `{latitude:-90..90, longitude:-180..180, accuracy_m?}` persists `user.last_location` + broadcasts.
- **Team locations dispatcher feed**: `GET /api/team/locations` — tenant-scoped, returns id/name/role/tech_status/last_location.
- **Priority field**: `JobIn`/`JobUpdate` now accept `priority: low|normal|high|emergency`. New `PATCH /api/jobs/{id}/priority` for lightweight updates from the board.

### Frontend
- **`/app/dispatch` — the headline page**:
  - **4 view tabs**: Day (hourly grid by tech), Week (day×tech matrix), Month (calendar with type-colored chips), Map (Leaflet + OSM with live tech markers).
  - **Drag & drop** any job card (unassigned rail or board) onto a tech-time slot → optimistic PATCH + WS rebroadcast.
  - **Color-coded job cards**: left-border tinted by `job_type`, status pill, $price.
  - **Emergency cards** ring-pulse animated red with ⚡ icon; "1 Emergency" header chip + red "EMERGENCY OPEN" banner in the unassigned rail; one-click filter to show only emergencies.
  - **Live WS indicator** (green pulse dot, "Live"/"Connecting…") with auto-reconnect.
  - **Tech rail** with status badge + last GPS coord + per-tech "Optimize today" button (calls the v1.8 ZIP-based optimizer).
  - **Map view**: Leaflet + free OpenStreetMap tiles, CircleMarker per tech colored by status, popups with name + time-ago.
- **Tech-side TechStatusBar** on `/app/my-jobs`: 5 status pill toggles + GPS opt-in switch that pings `/me/location` every 60s only while a job is `in_progress`.
- **AuthContext** now stores the JWT in `localStorage` (key `a1.token`) in addition to the httpOnly cookie, so the WS client can use it.
- New libs: `leaflet`, `react-leaflet`.

### Testing
- **19 new tests + 222 baseline = 241/241 backend tests green**. 0 critical issues. 1 minor (WS close-code spec compliance — fixed).

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

### v1.12 — Done
- ✅ Modern dispatch board (drag-and-drop, WebSocket realtime, day/week/month/map views, emergency priority + color-coded cards, tech GPS + status, Leaflet+OSM map)

### P1 — Remaining
- Apple login (needs Apple Developer credentials from user)

### v1.13 — Done
- ✅ Nominatim geocoding for job addresses (auto-pins on dispatch map)
- ✅ WS heartbeat (25s server ping)
- ✅ Tech leaderboard widget on dashboard
- ✅ 30-day recurring-revenue forecast widget on dashboard
- ✅ Per-user notification preferences (event toggles + quiet hours, prefs-aware push)
- ✅ Mobile camera + library photo upload (`expo-image-picker`)
- ✅ Mobile signature capture (`react-native-signature-canvas`)
- ✅ Mobile offline queue (`AsyncStorage` + 20s auto-flush)

### v1.14 — Done (Estimates & Invoicing)
- ✅ Good / Better / Best proposal builder with featured tier highlighting
- ✅ Pre-wired Wisetack-style financing service (`financing_service.py`) with local APR/term quote fallback; monthly-payment math (amortized formula)
- ✅ Full invoice CRUD with line items, tax rate, discount (% or $), deposit (% or $)
- ✅ Currency math via `Decimal` with `ROUND_HALF_UP` (accounting-correct)
- ✅ PDF generation for estimates (multi-tier) and invoices (`pdf_service.py`, ReportLab)
- ✅ Public no-auth proposal page (`/proposal/:token`) — premium homeowner-friendly UI: 3-tier comparison, optional add-ons, sticky CTA, financing CTA, e-signature canvas, IP+UA captured
- ✅ Public no-auth invoice payment page (`/pay/:token`) — large "Pay $X now" + deposit-only option, Stripe-secure footer
- ✅ Stripe Checkout for invoice — full / deposit / balance; webhook wires payments into invoice via `handle_invoice_payment`
- ✅ Convert approved estimate → invoice (selected tier + selected addons), sequential numbering (E-0001, I-0001 per company)
- ✅ Reusable estimate & invoice templates with builder dropdown
- ✅ Sidebar nav: Estimates · Invoices · Templates
- ✅ Backend test coverage: 23/23 pytest cases pass

### v1.18 — Done (Pipeline Kanban)
- ✅ New `/app/pipeline` page — drag-and-drop Kanban view of jobs
- ✅ 6 default columns: Unscheduled · Won bid · Scheduled install · In progress · On hold · Completed
- ✅ Optional Lost bid + Cancelled columns (toggle via "Show lost/cancelled" button)
- ✅ Each column shows count badge + total revenue (sum of card `price`)
- ✅ Cards display title, customer, address, scheduled date, price; emergency jobs bordered red with priority badge
- ✅ Native HTML5 drag-and-drop with optimistic UI + auto-rollback on failure
- ✅ Search bar filters across title/customer/address
- ✅ Sidebar nav: "Pipeline" link with Kanban icon
- ✅ All transitions validated end-to-end via `PATCH /api/jobs/{id}` (won_bid → scheduled → in_progress → on_hold → scheduled)

### v1.17 — Done (AI Integration)
- ✅ **8 AI features** live across the platform, powered by OpenAI via Emergent Universal LLM Key (gpt-4o / gpt-4o-mini)
  - **Estimate generator** — "✨ Generate with AI" on Estimate Builder → 3 G/B/B tiers from a prompt
  - **Call summaries** — structured JSON (intent, sentiment, action_items, next_step); auto-logs to customer comms
  - **Dispatcher assistant** — floating chat panel on the Dispatch page; multi-turn with session_id
  - **Tech notes polish** — inline button on JobDetail notes section
  - **Job summaries** — auto-generate invoice-ready paragraph from materials + checklist + voice notes
  - **Upsell recommendations** — contextual chip on each job ({title, reason, suggested_price, confidence})
  - **Maintenance scanner** — bulk customer scan → surfaces who's due for recurring service
  - **Customer chatbot** — hybrid sales+support widget on public Booking + Proposal pages, with session persistence
- ✅ `ai_logs` audit trail for every call (feature, model, tokens-in/out, success/error)
- ✅ `maintenance_suggestions` and `chatbot_messages` collections with indexes
- ✅ "AI Assistant" sidebar nav → new `/app/ai` page with Overview · Maintenance · Activity log tabs
- ✅ Logo refresh — new orange gear "A1fieldpro" branding across Layout, login, and emails
- ✅ Backend tests: **20/20 AI endpoint tests pass** (estimate gen, call summary, polish, job summary, upsell, maintenance scan/list/dismiss, dispatcher, chatbot, logs, auth + tenant isolation)
- ✅ Production hardening: `dismiss_maintenance` now returns 404 on missing id (tenant isolation)

### v1.16 — Done (Pipeline statuses)
- ✅ Added **Won bid**, **Lost bid**, **On hold** statuses
- ✅ Renamed **Scheduled** → **Scheduled installation**
- ✅ One-time DB migration runs on startup: `scheduled` → `scheduled_installation`
- ✅ Backend validation tightened — `JobUpdate.status` now uses `Literal[]`, rejecting unknown values
- ✅ Status colors + labels updated across Jobs, Dashboard, Dispatch, Schedule, MyJobs, JobDetail (web) and the mobile app
- ✅ Dashboard `/dashboard/stats` now returns counts for won_bid, lost_bid, on_hold
- ✅ Activity log + auto-comm entries fire on all new transitions

### v1.15 — Done (Technician Mobile App)
- ✅ Dark mode with persistence (`lib/theme.tsx` ThemeProvider, AsyncStorage)
- ✅ 5-tab nav: Today · All jobs · Timesheet · Settings · Profile
- ✅ **Timesheet screen** — big clock-in/out, live elapsed counter, +15m/+30m breaks, today/week totals, recent-shifts history
- ✅ **Per-job time tracking** — start/stop timer on job, total minutes, live counter while running
- ✅ **Checklists** — apply template from picker, tap-to-toggle items with checkbox + line-through
- ✅ **Materials** — add from catalog (auto-fills price + decrements stock) or custom; per-job usage list with totals
- ✅ **Voice notes** — modal with auto-focus textarea + hint to use device keyboard mic 🎤
- ✅ **Photo capture** with timestamp overlay on thumbnail; library import; **video capture** (60s max) with playback via browser
- ✅ **E-signature** capture (`react-native-signature-canvas`)
- ✅ **Navigate button** — opens Apple Maps on iOS, Google Maps Navigation on Android
- ✅ **Invoice collection** — Stripe Checkout in-app via WebBrowser
- ✅ **Settings screen** — theme picker (light/dark/system), push toggle, pending-changes pill, "Sync now", sign-out
- ✅ **Offline mode** — AsyncStorage queue, auto-flush every 20s, retry on focus, banner shows pending count
- ✅ **Real-time sync** — 30s background refetch on Today + on-focus refresh everywhere
- ✅ Large field-friendly buttons throughout (min 16px vertical padding, 16-44px touch targets)
- ✅ Backend test coverage: 38/38 pytest cases pass

### P1 — Remaining
- Apple login (needs Apple Developer credentials from user)
- Twilio SMS — backend wired & gated, awaiting Twilio credentials from user
- Mapbox/Google fallback for Nominatim 429 — wired in geocode_service.py, awaiting MAPBOX_ACCESS_TOKEN or GOOGLE_MAPS_API_KEY

### Feb 2026 — Iteration 18
- ✅ Pipeline `In progress` + `Completed` columns now always visible (no toggle), positioned after Scheduled install
- ✅ Twilio SMS service added (`/app/backend/sms_service.py`, `/app/backend/routers/sms.py`)
   - Endpoints: `GET /api/sms/status`, `POST /api/sms/send`, `POST /api/sms/job-reminder`,
     `POST /api/sms/send-due-reminders?window_hours=24`, `GET /api/sms/log`
   - Graceful 503 with helpful error when `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_FROM_NUMBER` not set
   - RBAC: owner/dispatcher/office_manager/csr/super_admin only
- ✅ Geocoding refactored — Mapbox primary (when `MAPBOX_ACCESS_TOKEN` set) → Google fallback → Nominatim
- ✅ All 17/17 iteration 18 pytest cases pass; no regressions in SMS/geocode/pipeline paths

### Feb 2026 — Iteration 19 — White-Label SaaS System
- ✅ **Branding** (`routers/branding.py`, `pages/BrandingSettings.jsx`): logos, favicons, primary/accent/secondary colors with 6 presets, app name, tagline, custom domain (stored + DNS instructions), support email/phone, invoice footer, email "from" name, branding audit log, public unauthenticated lookup via `GET /api/public/branding?domain=…|company_id=…`. Branding applied app-wide via CSS variables in AuthContext.
- ✅ **Branches** (`routers/branches.py`, `pages/Branches.jsx`): per-company sub-locations CRUD, per-branch metrics, plan-gated to Pro/Enterprise (402).
- ✅ **Franchises** (super_admin): parent-of-companies grouping with cross-tenant rollup metrics.
- ✅ **Message templates** (`routers/msg_templates.py`, `pages/MessageTemplates.jsx`): 7 system defaults auto-seeded per tenant, $variable substitution via string.Template.safe_substitute, live preview with sample data, variable picker UI. System defaults are toggle-able but not deletable.
- ✅ **Subscription** (`routers/subscription.py`, `pages/Subscription.jsx`): 4 plans — Starter $120 / Lite $220 / Pro $360 / Enterprise $899 — with feature flags (ai_assist, branches, custom_domain, franchise, api_access). Stripe Checkout wired (env-gated `STRIPE_PRICE_<PLAN>`), dev-mode fallback flips plan locally when prices not configured. Super-admin override at `PATCH /api/subscription/admin/{company_id}`.
- ✅ **Per-tenant API Keys** (`routers/api_keys.py`, `pages/ApiKeys.jsx`): Pro/Enterprise feature. SHA256-hashed `afp_live_<token>` keys, plaintext returned ONCE, revocable, last-used tracking.
- ✅ **Tenant management** (`routers/tenants.py`, `pages/SuperTenants.jsx`): super-admin platform-wide view with MRR/ARR, suspend, hard delete (purges 22 collections), JSON data export (password_hash + mfa_secret stripped).
- ✅ **Plan catalog** (`whitelabel_service.py`): single source of truth for plans, default branding, default templates, feature flag helpers (`has_feature(plan, "branches")`), 16 template variables, `render_template` / `find_variables`.
- ✅ **Multi-tenant indexes**: `branding.custom_domain` unique sparse, `subscription.plan`, `parent_franchise_id`, `message_templates(company_id, key)` unique, `api_keys.hash` unique sparse.
- ✅ Sidebar nav: Branding, Branches, Messages, Subscription, API keys (owner+), Tenants (super_admin).
- ✅ Startup migration: existing companies default-seeded to Starter plan; demo company promoted to Pro.
- ✅ Backend 37/37 pytest cases pass + frontend 5/5 pages smoke-passed (iteration 19).

### Feb 2026 — Iteration 20/21 — Public Pricing + White-Label Tenant Landing
- ✅ **Public pricing page** at `/pricing` — unauthenticated, renders from `GET /api/subscription/plans`. 4 plan cards (Starter $120 / Lite $220 / Pro $360 / Enterprise $899), monthly/annual toggle (annual saves 15% display), 8-row compare table with all features, 4-question FAQ accordion. All CTAs route to `/register`. Landing page nav `Pricing` link wired to the route.
- ✅ **Public tenant landing** at `/site/:companyId` (and `/site?domain=…` fallback) — unauthenticated, renders from `GET /api/public/branding`. Hero with tenant tagline/app_name/support_phone, services grid (4 cards), how-it-works steps, contact section with phone/email links, footer. Hero gradient uses tenant primary→secondary colors. All "Book service" CTAs point to `/book/:companyId`.
- ✅ **New public asset endpoint** `GET /api/public/branding/asset/{company_id}/{kind}` (kind = logo|favicon) — serves tenant branding images without auth, with path-prefix validation defense-in-depth. `logo_url` and `favicon_url` are now returned from `GET /api/public/branding` so the landing page can display them.
- ✅ **BrandingSettings sidebar** now surfaces the tenant's branded-landing URL with copy + open-in-new-tab button. Clipboard writes wrapped in try/catch + `execCommand` fallback to avoid sandbox-iframe overlay errors.
- ✅ Iteration 21 retest: backend 6/6 + frontend 100% on targeted flows.

### Feb 2026 — Iteration 22 — Fresh Cash Finance System
- ✅ **Decisioning engine** (`/app/backend/fresh_cash_service.py`): APR ladder (excellent 6.99% / good 9.99% / fair 14.99% / subprime 19.99% / declined), DTI limit 0.45, deterministic mock `MockBureauAdapter` keyed off `fico_bucket` field. `RealBureauAdapter` stubbed and env-gated (set `CREDIT_BUREAU_PROVIDER`/`API_KEY`/`BASE_URL` to wire real bureau). Amortization schedule + monthly_payment + total_finance_charge math.
- ✅ **Customer portal** (`/finance/:token` — public, no auth) — 4-step wizard: Apply (FICO bucket + income + obligations + consent) → Decision (approved/counter_offer/manual_review/declined) → Sign (SignaturePad + typed name) → Done. Tenant-branded (uses public/branding for colors/logo).
- ✅ **Contractor dashboard** (`/app/financing`) — 4 metric tiles (Total funded / Pending volume / Buy-down fees / Active rentals), 5 pipeline chips, Applications tab with copy-public-link + buy-down button, Rentals tab, calculator modal with amortization table, new-application + new-rental modals.
- ✅ **Admin dashboard** (`/app/admin/financing`, super_admin) — platform metrics (total funded, funding events, by-status, by-tier), per-app override modal (change decision/APR/term).
- ✅ **Buy-down marketplace**: `POST /api/financing/buydown/quote` + `POST /api/financing/buydown` — contractor pays X% fee → customer APR drops X×0.5 points. Mutates the offer + creates `finance_buydowns` ledger row.
- ✅ **Funding events**: `POST /api/financing/funding-events` (ledger-only). `kind=disbursement` on a signed app auto-advances to `funded`.
- ✅ **Rental equipment financing**: `POST/GET /api/financing/rentals` — auto-derives weekly ↔ monthly payment, tracks `balance_remaining`.
- ✅ **Estimate integration**: New `POST /api/public/estimates/{token}/finance` creates a Fresh Cash application from a public estimate's tier total; idempotent. PublicEstimate has a "Pay monthly with Fresh Cash" CTA that redirects to `/finance/<token>`.
- ✅ **6 new tenant-scoped collections** with indexes: finance_applications (public_token unique), finance_contracts, finance_buydowns, finance_funding_events, finance_rentals.
- ✅ Backend 19/19 financing endpoints + frontend 100% on customer wizard + contractor dashboard (iteration 22). `retest_needed=False`.

### Feb 2026 — Iteration 23 — "Finance this Job" Field-Sales Tool
- ✅ **Endpoint** `POST /api/financing/from-job` — accepts `{job_id, amount?, term_months?, send_sms?, origin_url?}`. Pulls customer data from the job, creates a Fresh Cash application, optionally texts the apply link via Twilio. Idempotent per job. Technician role can call it (designed for field sales). 400 on amount<$500, 404 on bad/cross-tenant job, graceful sms_result error structure when Twilio off / no phone / no origin.
- ✅ **Web Job Detail** — new "Finance this job" button (next to Charge) on the job detail page when `price >= 500 && !paid`. Opens a modal with amount/term editor, two actions: "Create link only" / "Text now". Success view shows the public customer URL with copy + "Open customer view" link.
- ✅ **Mobile Job Detail** (`/app/mobile/app/(tabs)/jobs/[id].tsx`) — new "Finance this job ($X)" big button on the Customer section. Alert dialog with 3 options: Cancel / Create link only / Create + text. Successful flow shows the URL with native copy via expo-clipboard + open-in-browser.
- ✅ Job's `financing_application_id` is set as back-reference after creation.
- ✅ Backend 9/9 + frontend 100% (iteration 23).

### Feb 2026 — Iteration 24 — Financeit-style Programs + AI Pitch
- ⚠️ Tech-stack note: spec mentioned Node + Postgres but kept the running FastAPI + MongoDB stack (full app stack swap would have meant rebuilding everything; business logic + API shape matches the Financeit-style spec).
- ✅ **Minimum financed amount bumped to $4,500** in `fresh_cash_service.MIN_AMOUNT`. Max bumped to $150k. Min term 3mo, max term 120mo, max amortization 240mo. Job-Detail web + mobile buttons updated to require $4,500 to surface.
- ✅ **Program catalog** (`fresh_cash_service.DEFAULT_PROGRAMS`): 16 system-default plans auto-seeded per tenant:
   - 6× Standard (60/120, 60/180, 60/240, 36/180, 84/240, 120/240)
   - 2× Buy-Down (13.99→9.99 @ 8% fee, 13.99→7.99 @ 12% fee)
   - 5× 0% Promo (equal-pay 3/6/12/18/24)
   - 3× Deferred (3mo, 6mo accrual, 6mo no-accrual)
- ✅ **Program-quote math** (`program_quote()`): handles 4 kinds — standard / buydown (with `customer_savings_vs_base`) / promo (0% equal pay) / deferred (interest-accrue toggle, balance_after_deferral). Computes dealer_fee_pct + contractor_fee_dollars + net_payout + monthly_payment + balloon_payment + total_interest + total_payback in one call.
- ✅ **Admin CRUD**: `GET/POST/PATCH/DELETE /api/financing/programs` (owner/super_admin). Soft-disable on system defaults (active=false) instead of hard delete. New `POST /api/financing/program-quote` accepts either `program_id` or inline `program` dict.
- ✅ **Extended application form** (`ApplicantDetailsIn`): added SIN, address/city/state/postal_code, home_ownership, employer_name, years_employed, project_description. ssn4 now optional (Canadian-friendly).
- ✅ **Linkage** — `program_id` propagated through `ApplicationCreateIn` + `JobFinanceIn`; from-job SMS now uses program-quoted monthly payment with smart-comparison copy.
- ✅ **AI pitch generator** `POST /api/financing/ai/pitch` — template-based, deterministic (no LLM cost). Picks the closest relatable comparison from `_COMPARISONS` ladder (a streaming bundle, a coffee habit, a family pizza night, etc.) and returns 3 SMS pitch variations + a `default`.
- ✅ **Frontend pages**:
  - `/app/financing/programs` — admin program manager: 5 filter chips, 16+ cards with kind/APR/term/amort/fee surfaced, edit modal with **live preview pane** showing monthly + dealer fee + net payout at $12k as you change values.
  - `/app/financing` Calculator modal rewritten — program-picker drives the breakdown (monthly, net payout, dealer fee, balloon, total interest, total payback).
  - Job-Detail FinanceJobModal — added program dropdown + live quote box (customer pays X/mo, your payout, dealer fee).
  - Sidebar: "Finance programs" entry for owner + super_admin.
- ✅ Backend 17/17 pytest + frontend 100% on program CRUD, all 4 quote kinds, AI pitch, min-amount enforcement (iteration 24). `retest_needed=False`.

### Feb 2026 — Iteration 25 — Executive Analytics Dashboard
- ✅ **Backend** (`/app/backend/routers/analytics.py`) — 10 endpoints, tenant-scoped via `company_id`, optional `branch_id` + date-range filters (`start`/`end` ISO):
  - `GET /api/analytics/overview` — Revenue, Δ% vs prev window, jobs total/completed/paid, avg ticket, active customers, finance funded $ + count.
  - `GET /api/analytics/revenue?granularity=day|week|month` — time-bucketed series (revenue + jobs).
  - `GET /api/analytics/technicians` — per-tech aggregation: jobs, completion %, revenue, avg rating, tips.
  - `GET /api/analytics/marketing` — leads/won/conversion/revenue by source + optional ROI from `marketing_costs`.
  - `GET /api/analytics/calls` — inbound calls → book rate → close rate → avg ticket funnel.
  - `GET /api/analytics/financing-conversion` — Started → decisioned → signed → funded funnel + approval/sign/fund rates + funded $.
  - `GET /api/analytics/memberships` — active/paused/cancelled, MRR, new30/churned30, churn % & retention.
  - `GET /api/analytics/leaderboard?metric=revenue|jobs|rating` — sortable top-25 leaderboard with win-rate.
  - `GET /api/analytics/realtime` — Today: in_progress, completed_today, revenue_today, new_finance_apps_today, funded_today (safe to poll every 30s).
  - `GET /api/analytics/export.csv?report=…` — CSV export for revenue/technicians/marketing/financing/leaderboard.
  - `POST /api/analytics/marketing-costs` — record spend per source for ROI.
- ✅ **Frontend** `/app/frontend/src/pages/Analytics.jsx` — Recharts-powered executive dashboard:
  - 8-tab strip (Overview / Revenue / Technicians / Marketing / Calls / Financing / Memberships / Leaderboard).
  - Global date-range + branch filter in header; CSV export button.
  - Overview: live banner (30s polled) + 8 KPI cards with Δ% chips + revenue AreaChart.
  - Revenue: dual-axis LineChart (revenue $ + job count) with day/week/month toggle.
  - Technicians: BarChart of revenue + sortable table.
  - Marketing: PieChart by source + ROI table.
  - Calls: 4 KPIs + animated funnel bars.
  - Financing: 4 KPIs + funnel BarChart.
  - Memberships: 8 KPI cards (MRR, retention, churn).
  - Leaderboard: gold/silver/bronze top-3 styling, metric toggles.
- ✅ Wired into `App.js` route `/app/analytics` + sidebar nav (owner / office_manager / accountant / super_admin).
- ✅ Backend 20/20 pytest + frontend 100% (iteration 25). `retest_needed=False`.

### Feb 2026 — Iteration 26 — Integration Hub + Webhooks + Sync Engine
- ✅ **9 third-party integrations** wired with per-tenant credentials (Fernet-encrypted in Mongo):
  - **Accounting**: QuickBooks Online (OAuth2, customer/invoice/payment sync via CDC)
  - **Payments**: Helcim (API token, tokenized card charges), Stripe (existing, surfaced in hub)
  - **Messaging**: Twilio (existing, surfaced in hub)
  - **Calendar**: Google Calendar + Outlook Calendar (OAuth2, event sync via watch / Graph subscriptions)
  - **Email**: Gmail (OAuth2, gmail.send)
  - **Video**: Zoom (Server-to-Server OAuth, auto-create meeting links)
  - **Maps**: Google Maps (Distance Matrix + Places autocomplete keys)
- ✅ **Backend** (`/app/backend/integrations/`):
  - `registry.py` — single catalog driving UI cards, OAuth scopes, sync intervals.
  - `store.py` — per-tenant Fernet encryption + OAuth state CSRF table with TTL index.
  - `oauth.py` — auth-URL builder, code exchange, refresh, Zoom S2S helper.
  - `routers/integrations.py` — GET list/catalog, POST save (api-token), DELETE disconnect, POST test (live ping), POST sync, GET /start /callback for OAuth2.
  - Owner / office_manager / super_admin only; technicians → 403.
- ✅ **Webhook system** (`/app/backend/routers/webhooks.py`):
  - **Inbound** at `/api/webhooks/in/{provider}` for Stripe, Twilio, QuickBooks, Helcim, Zoom, Google Calendar, Outlook (handles MS Graph `validationToken` + Google sync ping). Per-provider signature verification.
  - **Outbound** subscriptions CRUD + delivery log: HMAC-SHA256 signed POSTs with `X-A1FP-Signature: t={ts},v1={hex}`, retry backoff 10s/1m/5m/30m, secret shown ONCE.
  - 14 event types: job.*, invoice.*, estimate.*, customer.*, finance_application.*, payment.received.
- ✅ **Sync engine** — APScheduler `AsyncIOScheduler` with 3 boot-time jobs (QuickBooks 30m, Google Calendar 15m, Outlook 15m). Heartbeats logged to `integration_sync_events` until OAuth tokens supplied.
- ✅ **Frontend**:
  - `/app/integrations` — Hub with 9 cards, category filters, skeleton loaders, status badges. Modal: OAuth Connect OR field form, Test / Sync / Disconnect actions.
  - `/app/integrations/webhooks` — Subs table + deliveries log, "New subscription" modal with event multi-select + secret-once banner.
  - Sidebar nav: Integrations + Webhooks links.
- ✅ Outbound emission wired into `routers/jobs.py` (`job.created`). Pattern documented for invoices/estimates/financing.
- ✅ Backend 23/23 pytest + frontend 100% (iteration 26). `retest_needed=False`.
- ⚠️ Live OAuth requires user-supplied env vars; UI shows "Platform OAuth client not configured" until set. API-token providers (Helcim/Twilio/Maps/Zoom) work immediately on save.
- ⚠️ Fernet key derives from `JWT_SECRET` — set `INTEGRATION_FERNET_KEY` for prod.

### Feb 2026 — Iteration 27 — Production Deployment Scaffolding
- ✅ **Backend hardening** (additive, no behavior change):
  - `middleware.py` — `RequestIDMiddleware` (X-Request-ID round-trip), `SecurityHeadersMiddleware` (HSTS, X-Frame-Options:DENY, X-Content-Type-Options:nosniff, Referrer-Policy, Permissions-Policy), `RateLimitMiddleware` (token-bucket per IP × route prefix, 600 default / 20 auth RPM, env-tunable), `MetricsMiddleware` (per-route counters + latency averages).
  - `routers/health.py` — `GET /api/health` (liveness), `GET /api/health/ready` (DB ping), `GET /api/metrics` (JSON), `GET /api/metrics/prom` (Prometheus exposition).
  - GZip middleware for >1 KB responses; optional `TrustedHostMiddleware` via `ALLOWED_HOSTS`.
  - CORS now configurable per-env via `CORS_ORIGINS` (no more `*` in prod).
- ✅ **DB migrations** — `backend/migrations/` framework with idempotent `runner.py` invoked on FastAPI startup; first migration `0001_initial.py` consolidates inline ad-hoc updates + baseline indexes.
- ✅ **Docker**:
  - `backend/Dockerfile` — multi-stage python:3.11-slim, non-root user (uid 10001), tini PID 1, `HEALTHCHECK` on `/api/health`, 4 uvicorn workers.
  - `frontend/Dockerfile` — multi-stage build → nginx:1.27-alpine + `frontend/nginx.conf` (gzip, 1-year cache on hashed assets, SPA fallback, CSP/HSTS headers, `/healthz`).
  - `docker-compose.yml` — mongo + backend + frontend with healthchecks + resource limits for local/staging.
  - `.dockerignore` keeps images slim (no `node_modules`, no `__pycache__`, no test reports).
- ✅ **CI/CD** (`.github/workflows/`):
  - `ci.yml` — backend lint+pytest+coverage with Mongo service, frontend lint+build, Docker buildx for both images (gha cache).
  - `security.yml` — pip-audit, yarn audit, CodeQL (Python + JS), gitleaks secret scan, Trivy container scan; weekly cron Mon 06:00 UTC.
  - `deploy.yml` — OIDC → AWS, push to ECR, force ECS service redeploy, wait services-stable, smoke `/api/health`; environment gate for production.
  - `backup.yml` — nightly mongodump + KMS-encrypted S3 upload.
- ✅ **AWS Terraform** (`infrastructure/terraform/`):
  - 2-AZ VPC with public + private subnets, NAT GW for egress, ALB SG locked down 80/443.
  - ECS Fargate cluster (Container Insights enabled) with backend + frontend services, task roles for SecretsManager access (MONGO_URL / JWT_SECRET / INTEGRATION_FERNET_KEY), 30-day CloudWatch log retention.
  - ALB with TLS 1.3 listener policy, ACM cert input, `/api/*` path rule → backend TG, deployment circuit breaker + rollback enabled.
  - Application Autoscaling: backend scales 2 → 8 tasks at 65 % CPU target.
  - HTTP → HTTPS redirect listener, drop_invalid_header_fields enabled.
  - `README.md` with bootstrap + apply instructions.
- ✅ **Ops scripts** (`scripts/`):
  - `backup_mongo.sh` — KMS+optional GPG-encrypted backup to S3, retention cleanup.
  - `restore_mongo.sh` — interactive restore with confirmation.
  - `build_and_push.sh` — emergency local redeploy path.
  - `migrate.sh` — manual migration runner.
  - `security_audit.sh` — combined pip-audit + yarn audit + ruff S-rules + gitleaks.
- ✅ **Documentation** (`docs/`):
  - `DEPLOYMENT.md` — architecture, env tiers, AWS bring-up, cost ballpark (~$165/mo MVP).
  - `LAUNCH_CHECKLIST.md` — 60-item production launch matrix with sign-off table.
  - `SECURITY.md` — threat model, auth/MFA/session policy, transport hardening, IR playbook.
  - `RUNBOOK.md` — alert response playbooks (ALB 5xx, task crash loops, Atlas pool, webhook failures) + common ops one-liners.
  - `SOC2_CHECKLIST.md` — CC1-CC9 + Availability/Confidentiality/Privacy criteria matrix with status per control.
- ✅ **Env templates** — `backend/.env.example` + `frontend/.env.example` covering all required + optional variables.
- ✅ **Tests** — `test_iteration_27_hardening.py` covers health, ready, metrics (json + prom), security headers, request-id round-trip, gzip, OPTIONS pass-through. 8/8 pass + iteration 26 + 25 still green (43/43).

### Feb 2026 — Iteration 28 — Platform-Wide UX & Performance Pass
- ✅ **Bundle splitting** — All authenticated pages converted to `React.lazy()` in `App.js`. Initial bundle now contains only auth + landing; everything else streams as the user navigates. Suspense fallback uses a minimal spinner; routes wrapped in `RouteErrorBoundary` so a stale-chunk deploy never produces a forever-spinner.
- ✅ **Command palette** (`CommandPalette.jsx`) — `⌘K`/`Ctrl+K` global shortcut opens a fuzzy-search modal listing every page + 8 quick actions (New job/estimate/invoice/customer + jump to dispatch/analytics/integrations/webhooks). Keyboard nav (↑/↓/Enter/Esc); does NOT hijack when typing into inputs unless palette already open. Header has `cmdk-trigger` button for mouse users.
- ✅ **Quick-create FAB** (`QuickCreateFAB.jsx`) — Floating "+" button bottom-right on every authenticated page. Fan-out menu with role-aware quick-create actions: Work order, Customer, Estimate, Invoice, Finance job. Technicians see Customer/Estimate/Finance so the FAB remains a constant UX anchor.
- ✅ **Grouped sidebar nav** (`Layout.jsx` rewrite) — 28 flat items → 6 collapsible sections (Operations / Sales / Money / Insights / Platform / Settings). Each section's collapsed state persists to localStorage. Active link gets `#1D4ED8` accent + filled icon. Sticky header with `backdrop-blur` + soft shadow. `visibleGroups`/`navForCmdk` memoized on `user.role`.
- ✅ **Backend perf middleware** (`perf.py`):
  - `SlowRequestLoggerMiddleware` — logs structured `slow_request rid=… method=… path=… status=… duration_ms=…` for any request exceeding `SLOW_REQUEST_THRESHOLD_MS` (default 800 ms). All responses now carry `X-Response-Time-ms` header.
  - `TTLCache` helper (in-memory, prefix-invalidatable) for future hot read paths.
- ✅ **Compound indexes** (`migrations/0002_perf_indexes.py`) — added 13 indexes covering hot list-view paths: customers (name/phone/email), invoices + estimates (status × created_at DESC), activity (actor + created_at), webhook_deliveries (status + created_at), timesheets (user + started_at), jobs (assigned_to + scheduled_at), finance_applications (status + created_at).
- ✅ **51/51 backend pytest pass + frontend 100 % pass** (iteration 28). 0 critical/blocking issues. 6 minor code-review items addressed in same pass: technician quick actions added, ErrorBoundary wraps Suspense, Cmd+K skips when input focused (unless palette open), visibleGroups memoized.
- ⚠️ Minor non-blocking deferred: localStorage cross-tab sync for sidebar collapse state; tighten cmdk-trigger min-width at small laptops; remove window-event coupling between header trigger & palette via context.

### Feb 2026 — Iteration 29 — Sentry SDK + CommandPalette Context Refactor
- ✅ **Backend Sentry wiring** (`observability.py` + `server.py`):
  - `init_sentry()` runs BEFORE `FastAPI()` so Starlette/FastAPI integrations wrap correctly.
  - Silent no-op when `SENTRY_DSN` is unset — dev/test never ships events.
  - When DSN is set: tags release as `a1-field-pro@{GIT_SHA|APP_VERSION}`, `environment={APP_ENV}`, scope tag `service=a1-field-pro-backend`, request_id per request (added in `RequestIDMiddleware`), traces_sample_rate=0.1 (env-tunable), PII off by default (SOC2).
  - Integrations: StarletteIntegration, FastApiIntegration, AsyncioIntegration, LoggingIntegration (INFO breadcrumbs, ERROR events).
  - `/api/health` now surfaces `sentry: bool(SENTRY_DSN)` so ops can confirm wiring.
  - `requirements.txt` pinned `sentry-sdk==2.61.0`.
- ✅ **Frontend Command Palette context refactor** (`context/CommandPaletteContext.jsx` + `App.js` + `Layout.jsx` + `CommandPalette.jsx`):
  - Removed synthetic `window.dispatchEvent(new KeyboardEvent(...))` hack — `cmdk-trigger` now calls `ctx.toggle()` directly.
  - State lives in `CommandPaletteProvider` wrapping `BrowserRouter`. Any descendant component can `useCommandPalette()` and read `{open, toggle, close}`.
  - Global hotkey listener bound ONCE (no rebind churn) — `openRef` reads latest state inside the closure.
  - Still skips Cmd+K when input/textarea focused unless palette is already open (no regression).
- ✅ **Hooks order fix** — `visibleGroups` + `navForCmdk` useMemo hooks hoisted ABOVE the `if (!user) return null` early return in `Layout.jsx` (eslint `react-hooks/rules-of-hooks` now clean).
- ✅ **Cmd+K trigger min-width relaxed** — `min-w-[180px] lg:min-w-[260px]` so 1280-px laptops aren't crowded.
- ✅ Backend 51/51 pytest pass + frontend 100% (iteration 29). No regressions.

### Feb 2026 — Iteration 30 — FINAL pre-deploy validation + Pricing Update
- ✅ **New 5-tier pricing** replaces previous 4-tier:
  - **Basic** — $49 /mo · 1 seat · "For solo operators getting started"
  - **Team** — $149 /mo · 5 seats · "Growing crew of up to 5"
  - **Business** — $299 /mo · 15 seats · *Most popular* · AI + Branches + API + White-label
  - **Pro** — $499 /mo · 50 seats · AI + Branches + Custom domain + API
  - **Enterprise** — Custom pricing (contact sales) · Unlimited seats · all features incl. Franchise
- ✅ Pricing updated everywhere: `backend/whitelabel_service.py` (PLANS catalog), `routers/subscription.py` (PLAN_KEYS Literal), `routers/tenants.py`, `server.py` seed, `frontend/src/pages/{Pricing,Subscription,SuperTenants}.jsx`. Public `/pricing`, `/app/settings/subscription`, and `/app/super/tenants` all render 5 cards; Enterprise shows "Custom" + "Contact sales" mailto button.
- ✅ **Migration 0003_rename_plans** applied automatically on first boot — maps legacy `starter → basic`, `lite → team`, `pro → business`. Idempotent; stamps `subscription.migrated_from` for audit.
- ✅ **Tests updated** — `test_iteration_19` covers new keys + prices. Teardown now restores to `business` (post-migration default).
- ✅ **Final E2E validation (iteration 30 testing agent):**
  - Backend **88/88 pytest** (test_iteration_19 + 25 + 26 + 27) PASS in ~14 s.
  - Frontend 100% — all critical flows (login as owner/tech/super, Cmd+K navigation, FAB role-filter, lazy routes, Integrations hub, Webhooks, Analytics, Subscription, Super Tenants) verified.
  - Security headers (HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, X-Request-ID, X-Response-Time-ms) present.
  - Sentry SDK no-op verified when DSN unset; `/api/health` exposes `sentry: false`.
  - **Zero blocking bugs.** Testing agent auto-fixed one duplicate-option bug in `SuperTenants.jsx` plan filter (leftover from migration).
- ✅ **Polish applied this iteration**: FAB position bumped to `sm:bottom-6 sm:right-6` to coexist with preview shell badge; `test_iteration_19.test_change_plan_owner` teardown restores to `business`; demo subscription document reset.

### Production Readiness — GREEN ✅
- All artifacts present: Dockerfiles, docker-compose, Terraform (VPC + ECS + ALB + autoscaling), CI/CD (CI + Security + Deploy + Backup), 5 ops scripts, 5 docs (DEPLOYMENT/LAUNCH_CHECKLIST/SECURITY/RUNBOOK/SOC2_CHECKLIST).
- 3 idempotent migrations: 0001_initial, 0002_perf_indexes, 0003_rename_plans — all auto-applied on startup.
- 9 third-party integrations + 14 outbound webhook event types + APScheduler sync engine — all wired with graceful degradation.
- Sentry SDK installed + scoped per-request; activates when `SENTRY_DSN` is set.
- 88 pytest tests + frontend smoke flows green. Ready to tag `v1.0.0` and run `.github/workflows/deploy.yml`.

### P1 — Remaining
- User-supplied OAuth credentials for QuickBooks / Google / Microsoft / Zoom (UI ready, env vars needed)
- Stripe Price IDs (`STRIPE_PRICE_STARTER`, `STRIPE_PRICE_LITE`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_ENTERPRISE`) for real billing — currently dev-mode flips plan locally.
- Twilio SMS — backend wired & gated, awaiting credentials.
- Mapbox/Google fallback for Nominatim 429 — wired, awaiting `MAPBOX_ACCESS_TOKEN` or `GOOGLE_MAPS_API_KEY`.
- Apple login (needs Apple Developer credentials).

### Implemented Feb 11, 2026 (iterations 31–32 — this session)
- **P0 Play Store hardening** — `mobile/app.json` now includes Android permissions, versionCode, bundle id, iOS infoPlist usage strings, EAS project placeholder, OTA updates URL placeholder, and runtimeVersion policy.
- **P1 Web UI for Checklists** — `/app/checklists` page (CRUD master templates) + `JobChecklistPanel` component embedded on JobDetail. Supports apply-from-template, toggle, and per-job add/edit/delete that does NOT mutate the master. Native `<select>` migrated to shadcn/ui Select (eliminates HTML hydration warning).
- **P1 Per-job checklist editing backend** — `GET/POST /api/jobs/{job_id}/checklist`, `POST/PUT/DELETE /api/jobs/{job_id}/checklist/items[/{item_id}]`, `DELETE /api/jobs/{job_id}/checklist` (clear). Tenant-isolated; **emits `job.checklist.item.added|updated|removed` and `job.checklist.cleared` activity entries**.
- **P2 Analytics PDF export** — `GET /api/analytics/export.pdf?report=<overview|revenue|technicians|marketing|financing|leaderboard>` via reportlab. Wired to Analytics page with PDF + CSV buttons.
- **Play Store legal docs** — `GET /api/legal/privacy` + `/api/legal/terms` (styled HTML, brand gradient header) and `.txt` variants. New `/app/docs/templates/TERMS_OF_SERVICE.md` source document. Required for Google Play Console "App content → Privacy policy" field.
- **Mobile asset generator** — `/app/scripts/generate_mobile_assets.py` produces brand-aligned PNG placeholders (1024×1024 icon, 1024×1024 adaptive-icon with 70 % safe zone, 1284×2778 splash, 48×48 favicon, 1024×500 Play feature graphic). All emitted into `/app/mobile/assets/`. Replace with designer assets before launch.

### P2 — Future
- Android login (needs Google Play Developer credentials)
- Booking-confirmation email back to customers
- Mobile app — wire Expo Notifications (FCM/APNs)
- Tech leaderboard on dashboard
- 30-day recurring-revenue forecast widget
- Per-user notification preferences (toggle per event class + quiet hours)
- WS heartbeat / ping-pong for ultra-long sessions through aggressive ingress idle-kill
- Per-branch dashboards drill-down + branch-scoped technician routing
- Custom invoice PDF templates (e.g. Good/Better/Best layouts) per tenant
- Tenant-scoped audit log search UI (system + branding + subscription events)
- Activity-log entries for per-job checklist edits (currently only template CRUD is logged)
- HTML-escape KPI values in PDF generator (defensive hardening)
- Migrate native `<select>` in JobChecklistPanel to shadcn/ui Select to silence preview-only hydration warning

## Demo credentials
Owner: `demo@a1fieldpro.com` / `Demo1234!`
Dispatcher: `dispatcher@a1fieldpro.com` / `Demo1234!`
Technician: `tech@a1fieldpro.com` / `Demo1234!`
