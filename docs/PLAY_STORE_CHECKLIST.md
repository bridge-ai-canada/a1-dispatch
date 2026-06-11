# Google Play Store Launch Checklist — A1 Field Pro Mobile

> Time to ship: ~5-7 business days from "I have a Play Console account" to
> "app is live in Production track". Below is the exact sequence.

## Status snapshot

| Item | Status | Owner |
|---|---|---|
| Expo app scaffold (React Native + Expo SDK 51) | ✅ Built | — |
| Job CRUD / Schedule / Finance flows | ✅ Built | — |
| `app.json` with bundle id `com.a1fieldpro.mobile` | ✅ Configured | — |
| `eas.json` build/submit configuration | ✅ Just added | — |
| **App icon** (1024×1024 PNG) | ❌ **MISSING** | You |
| **Adaptive icon foreground** (432×432 transparent PNG) | ❌ MISSING | You / designer |
| **Feature graphic** (1024×500 PNG) | ❌ MISSING | Designer |
| **Phone screenshots** (≥ 2, 1080×1920 or 16:9) | ❌ MISSING | You |
| **Tablet screenshots** (optional but recommended) | ❌ MISSING | You |
| **Privacy policy URL** | ❌ **REQUIRED** | You (hosted) |
| **Google Play Console account** ($25 one-time) | ❌ Required | You |
| **Firebase project + google-services.json** (for FCM) | ❌ Required if push wanted | You |
| **EAS account** (free for solo, $99/mo for teams) | ❌ Required | You |
| **OAuth client ID for Android** (Google sign-in) | ⚠ Optional | You |
| **Data Safety form** answers | ❌ Required | You |
| **Content rating** (IARC questionnaire) | ❌ Required | You |
| **Store listing copy** (title, short desc, full desc) | ✅ Drafted below | — |

---

## Step 1 — Sign up for required accounts (Day 1, ~1 hour)

| Account | URL | Cost | Why |
|---|---|---|---|
| **Google Play Console** | play.google.com/console | $25 one-time | Submit + manage Android apps |
| **Expo / EAS** | expo.dev | Free → $99/mo | Cloud builds + submit |
| **Firebase** (optional, for push) | firebase.google.com | Free tier | FCM push notifications |
| **Google Cloud Console** | console.cloud.google.com | Free | OAuth (Google sign-in) + Maps |

Tips:
- Use a dedicated **Google Workspace account** for the dev account (e.g. `apps@a1fieldpro.com`) so it doesn't depend on a single person's personal Gmail.
- Play Console signup requires a credit card and government ID verification — allow 24–48 hrs for them to approve your developer account.

## Step 2 — Generate missing assets (Day 1–2)

You need 4 image files **before** you can submit. The repo has none of these yet (`assets/` only has a README).

| File | Size | Format | Where it's used |
|---|---|---|---|
| `assets/icon.png` | 1024×1024 | PNG (no transparency) | App icon on iOS & fallback on Android |
| `assets/adaptive-icon.png` | 1024×1024 (foreground), padding 432×432 safe zone | PNG, transparency OK | Adaptive Android icon (replaces `icon.png` on Android per `app.json`) |
| `assets/splash.png` | 1284×2778 or larger | PNG | Splash screen — use logo on solid background |
| **Play Store assets** | | | |
| Feature graphic | 1024×500 | JPG/PNG | Top banner on store listing |
| Phone screenshots ×8 max | 1080×1920 portrait OR 1920×1080 landscape | JPG/PNG | Store listing |
| 7-inch tablet ×8 max (optional) | 1200×1920 | JPG/PNG | Store listing |
| 10-inch tablet ×8 max (optional) | 1920×1200 | JPG/PNG | Store listing |

**Quickest path:** Use Figma → AppIcon Generator plugin OR use a $10 Fiverr designer for a 24-hr turnaround.

For screenshots, use `eas build --profile preview --platform android`, install the APK on your phone, then take real screenshots of:
- Login screen
- Dashboard
- Job detail with map
- "Finance this job" modal
- Schedule view

## Step 3 — Host a privacy policy (Day 1, ~30 min)

**Required by Play Store** for any app that collects user data (yours does — name, email, location, etc.).

Options:
- Use a generator: termly.io or privacypolicies.com ($0–$25/mo)
- Host on your marketing site at `https://a1fieldpro.com/privacy`
- Or push the template at `docs/templates/PRIVACY_POLICY.md` (generated below) to your site

## Step 4 — Configure push notifications (Day 2, optional)

Web push (VAPID) is already built — but **Android needs FCM, not VAPID**. To enable push on Android:

1. Create Firebase project, add Android app with package `com.a1fieldpro.mobile`
2. Download `google-services.json`, place at `/app/mobile/google-services.json`
3. Add to `app.json` plugins:
   ```json
   "android": {
     "googleServicesFile": "./google-services.json",
     "package": "com.a1fieldpro.mobile",
     "adaptiveIcon": { ... }
   }
   ```
4. Backend: add FCM server-key support to `push_service.py` (currently web-VAPID-only)

**Recommendation**: ship v1.0.0 WITHOUT push and add it in v1.1.0 a week later. You'll get to market faster and most field-service apps work fine with email + SMS notifications.

## Step 5 — Set up EAS and build (Day 3)

```bash
cd /app/mobile
npm install -g eas-cli@latest
eas login
eas build:configure                # confirms eas.json
eas build --profile production --platform android
# Wait ~15-30 min for cloud build to finish
# EAS outputs an .aab file — that's what you submit to Play Console
```

First time EAS asks to generate a keystore — **let it manage the keystore** (recommended unless you need legacy compatibility). Google Play App Signing then takes the upload key and signs the app on Google's side.

## Step 6 — Internal Testing track (Day 4)

Don't go straight to Production. Use the **Internal Testing** track first.

1. Play Console → App → Testing → Internal testing → Create new release
2. Upload the `.aab` from EAS
3. Add ≤ 100 tester emails (yourself + your team)
4. Submit → instant approval (no review for internal track)
5. Testers receive an email with the install link

**Test on at least 3 real devices**:
- One Pixel-line phone (stock Android)
- One Samsung phone (most popular vendor)
- One older device (Android 9 / API 28 if you can find one)

## Step 7 — Closed Testing → Open Testing → Production (Day 5–7)

| Track | Audience | Review time | When to use |
|---|---|---|---|
| Internal | ≤ 100, allow-listed emails | None | Daily team testing |
| Closed | Multiple lists, invitation | ~1 hr | Beta with first 5–20 paying customers |
| Open | Anyone with the opt-in link | ~1 day | Public beta |
| Production | Everyone | 1–7 days first review, hours after | Final live |

**Recommended sequence:**
- Day 4: Internal track (team smoke test)
- Day 5: Closed track (5 paying customers)
- Day 6: Submit Production track (first review)
- Day 7+: Listen for review verdict, fix any issues

## Step 8 — Data Safety + Content Rating (during submission)

These are forms inside Play Console. Plan to spend ~1 hour total filling them out.

**Data Safety** asks about every data type you collect. For A1 Field Pro:
| Data type | Collected? | Shared with 3rd parties? | Purpose | Optional? |
|---|---|---|---|---|
| Name | ✅ Yes | No | Account creation | No |
| Email | ✅ Yes | No | Account + notifications | No |
| Phone number | ✅ Yes | Twilio (delivery only) | SMS reminders | Yes |
| Address | ✅ Yes | Mapbox/Google (geocoding only) | Display job site | No |
| Photos | ✅ Yes (job photos) | No | Job documentation | Yes |
| Approximate location | ✅ Yes | No | Show nearby jobs | Yes |
| Precise location | ✅ Yes | No | Route optimization | Yes |
| Payment info | ❌ No (Stripe-hosted) | Stripe | We never see card data | N/A |
| Financial info (loans) | ✅ Yes | Wisetack-style processor | Soft credit | Yes |

**Content rating** answer "no" to everything except possibly "user-generated content"
(customer notes). Likely PEGI 3 / Everyone.

## Step 9 — Store listing copy

Copy & paste into Play Console → Store presence → Main store listing.

**Title (30 chars max):**
```
A1 Field Pro
```

**Short description (80 chars max):**
```
Scheduling, dispatch, invoicing & financing for field service pros.
```

**Full description (4000 chars max):**
```
A1 Field Pro is the modern operating system for HVAC, plumbing, electrical,
garage door, appliance repair, and any field service business. Built by
people who've actually run service trucks.

FOR OFFICE & DISPATCH
• Drag-and-drop schedule board with crew availability
• Smart dispatch — assign the right tech to the right job in seconds
• Customer database with full job history
• Recurring jobs for tune-ups & service agreements
• Public booking widget you embed on your website

FOR TECHNICIANS IN THE FIELD
• Today's jobs at a glance with one-tap navigation
• Photo capture before/after each visit
• Signature capture for completed work
• "Finance this job" — send a Fresh Cash application via SMS to the
  customer right from the truck (Wisetack-style soft credit)
• Offline-ready — keep working in the basement, sync when you're back

FOR THE OWNER
• Executive analytics dashboards (revenue, tech leaderboard, marketing ROI)
• Live financing funnel — see applications, approvals, funded jobs
• Membership programs with automatic recurring billing
• White-label your customer portal with your logo & colors

INTEGRATIONS
• QuickBooks Online — two-way customer & invoice sync
• Stripe — credit-card processing + recurring billing
• Helcim — alternative card processor with lower rates
• Twilio — SMS appointment reminders
• Google Calendar & Outlook — sync jobs to your team's calendars
• Gmail — send appointment confirmations from your own address
• Zoom — auto-create video links for virtual estimates
• Google Maps — distance matrix + address autocomplete

SECURITY & RELIABILITY
• SOC2-ready architecture
• 9 roles with granular permissions
• Multi-factor authentication
• Encryption at rest + TLS 1.2+ everywhere
• 99.9% uptime SLA

PRICING
• Basic — $49/mo (1 seat)
• Team — $149/mo (5 seats)
• Business — $299/mo (15 seats, AI assistant included)
• Pro — $499/mo (50 seats, custom domain)
• Enterprise — Custom pricing for franchises

Free 14-day trial. No credit card to start.

Built by field-service operators, for field-service operators.
Questions? hello@a1fieldpro.com
```

**Category:** Business
**Tags:** field service, dispatch, invoicing, scheduling, technician

## Step 10 — Required policies you must agree to

- [ ] Developer Distribution Agreement (Play)
- [ ] US Export Compliance
- [ ] Sensitive permissions justification (location, camera) — write 1-2 sentences explaining why you need each in the Play Console form

## After launch — keep these green

| Cadence | Task |
|---|---|
| **Each release** | Bump `version` in `app.json`, run `eas build --profile production --platform android`, run `eas submit -p android --latest` |
| **Monthly** | Review Play Console "Pre-launch report" (auto-runs your APK on Firebase Test Lab) |
| **Quarterly** | Review crash-free user rate; target ≥ 99.5% |
| **Annually** | Bump `targetSdkVersion` to current — Play requires you stay within 1 year of latest (currently API 34) |

## TL;DR — exact next 4 commands

```bash
# 1. Generate icon/feature-graphic (Figma or Fiverr)
# 2. Host privacy policy at a1fieldpro.com/privacy
# 3. Create accounts: Play Console + Expo
# 4. Then:
cd /app/mobile
npm install -g eas-cli
eas login
eas build --profile production --platform android
# wait, then:
eas submit -p android --latest
```

That's it. Welcome to the Play Store. 🎉
