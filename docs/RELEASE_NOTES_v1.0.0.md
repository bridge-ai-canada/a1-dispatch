# A1 Field Pro v1.0.0 — Production Launch

**Release date:** [LAUNCH DATE]

This is the first production release of A1 Field Pro — an end-to-end
SaaS platform for field service businesses. Built for HVAC, plumbing,
electrical, garage doors, and any operation that schedules technicians.

---

## 🎉 What you get

### Operations
- **Work orders** with status pipeline (unscheduled → scheduled → in progress → completed → paid)
- **Custom Kanban pipeline** for sales stages
- **Dispatch board** with technician map and drag-to-assign
- **Recurring jobs** (weekly tune-ups, quarterly service contracts)
- **Customer portal** at `/portal` — view jobs, pay invoices, schedule

### Sales & Estimating
- **Estimate builder** with line items, tax, signatures
- **AI-assisted descriptions** (OpenAI GPT-4o via Emergent LLM)
- **Public proposal links** with one-click sign + pay
- **Templates** for fast quoting

### Money
- **Invoices** + Stripe checkout + Stripe customer portal
- **Fresh Cash financing** (Wisetack-style) — soft credit, 4 program types
  (Standard / Buy Down / 0% Promo / Deferred), AI-generated pitches
- **"Finance this job"** SMS from any tech in the field
- **5-tier subscription** (Basic / Team / Business / Pro / Enterprise)

### Insights
- **Executive Analytics** — Revenue, Tech performance, Marketing ROI,
  Call funnel, Financing funnel, Memberships, Leaderboard, Realtime banner
- **Reports** with CSV/PDF export

### Platform
- **9 third-party integrations**: QuickBooks, Helcim, Stripe, Twilio,
  Google Calendar, Outlook Calendar, Gmail, Zoom, Google Maps
- **Webhook system**: 14 outbound event types (HMAC-signed, auto-retry)
  + inbound receivers for Stripe/Twilio/QuickBooks/Helcim/Zoom/Calendars
- **Sync engine**: APScheduler-driven, configurable per-provider
- **API keys**: per-tenant programmatic access
- **White-label SaaS**: tenant landing pages, custom branding, franchise
  rollups (Enterprise tier)
- **Super-admin tenant management** for platform operators

### Quality of life
- **⌘K / Ctrl+K Command Palette** — jump anywhere in 2 keystrokes
- **Floating Quick-Create FAB** — Work order / Customer / Estimate /
  Invoice / Finance job from any page, role-filtered
- **Grouped collapsible sidebar** (6 sections, localStorage-persisted)
- **Lazy-loaded routes** — fast initial paint, per-page chunks
- **Smart skeletons + animations** throughout
- **Mobile-optimized** — sidebar drawer + touch-friendly FAB

### Mobile app (Expo React Native)
- **iOS + Android** — Schedule, jobs detail, photo capture, signatures
- **"Finance this job"** button on every job
- **Offline-ready** local job cache

### Reliability & Ops
- **Multi-AZ AWS deployment** (ECS Fargate + ALB + Atlas)
- **Auto-scaling** 2 → 8 tasks at 65% CPU
- **Sentry-ready** error tracking (set `SENTRY_DSN`)
- **Prometheus / JSON metrics** at `/api/metrics{,/prom}`
- **Slow-request log** (>800 ms) for performance triage
- **Nightly KMS-encrypted backups** to S3
- **Rate limiting** (auth 20 RPM, default 600 RPM, env-tunable)

### Security
- **9 roles** with granular RBAC
- **MFA enforced** for owner / super_admin / office_manager
- **Per-tenant Fernet encryption** of integration secrets
- **HTTPS + HSTS + CSP** end-to-end
- **Brute-force protection** + account lockout
- **Tenant isolation** tested at every router
- **Audit log** for every privileged action
- **SOC2-ready** (see `docs/SOC2_CHECKLIST.md`)

---

## 📊 By the numbers

| Metric | Value |
|---|---|
| Backend tests passing | **88 / 88** |
| Frontend critical flows passing | **100 %** |
| API endpoints | ~180 |
| Pages | 52 (all lazy-loaded) |
| Mongo collections | 30+ |
| Integrations | 9 |
| Webhook event types | 14 |
| Migrations | 3 (idempotent) |
| Ops docs | 6 (DEPLOYMENT, LAUNCH, SECURITY, RUNBOOK, SOC2, SOC2_KIT) |
| Lines of code | ~85 000 |

---

## 🆕 Pricing

| Plan | Price | Seats | Highlights |
|---|---:|---:|---|
| Basic | $49 / mo | 1 | Solo operators |
| Team | $149 / mo | 5 | Up to 5 techs |
| **Business** ⭐ | $299 / mo | 15 | + AI · Branches · API |
| Pro | $499 / mo | 50 | + Custom domain |
| Enterprise | Custom | Unlimited | Franchise + everything |

---

## ⚙ Configuration required after deploy

| Env var | Required? | Notes |
|---|---|---|
| `MONGO_URL` | ✅ | Atlas connection string |
| `JWT_SECRET` | ✅ | 48-byte hex |
| `INTEGRATION_FERNET_KEY` | ✅ (prod) | `Fernet.generate_key()` |
| `STRIPE_API_KEY` | ✅ for payments | `sk_live_…` |
| `STRIPE_WEBHOOK_SECRET` | ✅ for payments | `whsec_…` |
| `RESEND_API_KEY` | ✅ for email | + verified sender |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | ✅ for SMS | |
| `MAPBOX_ACCESS_TOKEN` | optional | Geocoding fallback |
| `QUICKBOOKS_CLIENT_ID` / `QUICKBOOKS_CLIENT_SECRET` | optional | Per integration |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional | Calendar + Gmail |
| `MS_GRAPH_CLIENT_ID` / `MS_GRAPH_CLIENT_SECRET` | optional | Outlook |
| `ZOOM_CLIENT_ID` / `ZOOM_CLIENT_SECRET` / `ZOOM_WEBHOOK_SECRET_TOKEN` | optional | |
| `HELCIM_API_KEY` / `HELCIM_WEBHOOK_VERIFIER` | optional | |
| `SENTRY_DSN` | optional | Auto-no-op if unset |
| `RATE_LIMIT_DEFAULT_RPM` / `RATE_LIMIT_AUTH_RPM` | optional | Defaults 600 / 20 |

---

## 🐛 Known limitations

- Provider sync handlers (QuickBooks CDC, Calendar incremental) are
  heartbeat-only stubs until live OAuth tokens flow through
- Outbound webhook retry queue is in-process (lost on pod restart) —
  schedule a follow-up to persist in Mongo
- Frontend Sentry SDK not wired (backend Sentry only) — set
  `REACT_APP_SENTRY_DSN` later for client-side errors
- Apple/Google mobile sign-in pending dev credentials
- Tax calculations use a single-tier rate (no Avalara/TaxJar yet)

---

## 🙏 Thank you

Building a category-leading SaaS in one quarter is no small thing. To
the early team and the first 5 customers who took a chance on us:
this is for you. Let's go.

— [Founder name]
