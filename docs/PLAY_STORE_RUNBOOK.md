# Play Store Submission Runbook — A1 Field Pro

> 3 hours of active work spread over 3-5 days (the long part is Google verifying your dev account).

---

## Day 1 — Sign up (45 min active + 24-48 hr wait)

1. Play Console → https://play.google.com/console/signup ($25 one-time, ID verification)
2. Expo → https://expo.dev/signup (use username `a1fieldpro`)
3. Firebase → https://console.firebase.google.com/ (project: "A1 Field Pro", Android app: `com.a1fieldpro.mobile`, download `google-services.json`)
4. Google Cloud → https://console.cloud.google.com/ (enable Maps SDK for Android + Geocoding API, create Android OAuth client AFTER step 2)

## Day 2 — EAS init (15 min) — LOCAL MACHINE ONLY

```bash
cd <repo>/mobile
npm install -g eas-cli
eas login                # opens browser
eas init                 # writes real projectId into app.json
git add app.json && git commit -m "chore(mobile): mint EAS project ID" && git push
```

## Day 2-3 — Build & screenshot (60 min)

```bash
eas build --profile preview --platform android   # ~15 min cloud build
# Download APK link, install on phone, take screenshots:
#   1080×1920 portrait, min 2 / max 8
```

**Recommended 6 screens to capture:**
1. Dashboard (showing KPIs + revenue chart)
2. My Jobs — Today (techn view, 2-3 jobs visible)
3. Job Detail (photo + signature + Charge button visible)
4. Schedule (week view with drag-drop chips)
5. Customer Detail (with recent jobs list)
6. Settings → Branding (shows the white-label value prop)

> Use [previewed.app](https://previewed.app) (free) to drop these into device mockups with a 1-line subtitle — boosts conversion ~3x vs. raw screenshots.

## Day 3 — Production build & upload

```bash
eas build --profile production --platform android   # ~15 min — AAB (Android App Bundle)
eas submit --profile production --platform android  # uploads to Play Console internal-test track
```

First-time submit will prompt for:
- Play Console service-account JSON (one-time setup, see https://docs.expo.dev/submit/android/)

## Day 3-5 — Fill out Play Console & submit for review

In **Play Console → Your app**, fill these tabs:

### App content (left sidebar)
| Section | Action |
|---------|--------|
| **Privacy policy** | URL: `https://<your-public-domain>/api/legal/privacy` |
| **App access** | Provide test login: `demo@a1fieldpro.com` / `Demo1234!` |
| **Ads** | "No ads" |
| **Content rating** | Run IARC questionnaire (≈ 10 min, all "No" answers — pure productivity app, rating: Everyone) |
| **Target audience** | "18 and over" (business users) |
| **Data safety** | See `DATA_SAFETY_ANSWERS.md` (below) |

### Main store listing
| Field | Value |
|-------|-------|
| **App name** | A1 Field Pro |
| **Short description** (80 chars) | Dispatch, schedule, invoice & get paid — field service management. |
| **Full description** (4000 chars) | See `STORE_LISTING.md` (below) |
| **App icon** | `mobile/assets/icon.png` (1024×1024) |
| **Feature graphic** | `mobile/assets/play-feature.png` (1024×500) |
| **Phone screenshots** | Upload 2-8 from step 3 |
| **Application category** | Business |
| **Tags** | Productivity, Business, Tools |
| **Email** | support@a1fieldpro.com |
| **Website** | https://a1fieldpro.com |

### Release → Internal testing (recommended first track)
- Add yourself + 5-10 trusted testers (email list)
- Upload the .aab from `eas build --profile production`
- Roll out → testers install via Play Store testing link → use for a week before promoting to Production

Promote to **Production** track once internal testing is happy. Google review takes 1-7 days for first submission.

---

## Data Safety answers (copy-paste into Play Console)

| Question | Answer |
|----------|--------|
| Does your app collect user data? | **Yes** |
| Is data encrypted in transit? | **Yes** (HTTPS only) |
| Can users request data deletion? | **Yes** — via in-app Settings → Delete account |
| **Personal info: Name** | Collected · Required · Used for App functionality (account creation) |
| **Personal info: Email** | Collected · Required · Used for App functionality, Account management |
| **Personal info: Phone number** | Collected · Optional · Used for App functionality (SMS notifications) |
| **Personal info: Address** | Collected · Optional · Used for App functionality (job site routing) |
| **Financial info: Payment info** | Processed by Stripe (third party, not collected by us) |
| **Photos and videos: Photos** | Collected · Optional · Used for App functionality (job site photos) |
| **Location: Approximate location** | Collected · Optional · Used for App functionality (route optimization) |
| **Location: Precise location** | Collected · Optional · Used for App functionality (turn-by-turn nav to jobs) |
| **App activity: App interactions** | Collected · Required · Used for Analytics |
| **App info and performance: Crash logs** | Collected · Required · Used for Analytics (Sentry) |
| Data sharing with third parties? | **Yes** — Stripe (payments), Twilio (SMS), Sentry (crash logs), each with own privacy policy |

---

## Common rejection reasons (avoid these)

1. ❌ **Missing privacy policy URL** → ✅ Already hosted at `/api/legal/privacy`
2. ❌ **App crashes on launch** → ✅ Run `eas build --profile preview` and smoke-test on a real device first
3. ❌ **Permissions not justified** → ✅ Our `app.json` `infoPlist` + `permissions` arrays already have user-facing reasons
4. ❌ **Test account doesn't work** → ✅ Demo Owner credentials provided in App content → App access
5. ❌ **Screenshots show debug UI** → ✅ Don't use `--profile development`; only use `preview` or `production`
6. ❌ **Target API level too old** → ✅ Expo SDK 51 targets Android 14 (level 34) automatically — OK
7. ❌ **App bundle not signed** → ✅ EAS handles signing automatically with `eas build`

---

## Quick reference — EAS command cheatsheet

```bash
# Build
eas build --profile preview --platform android      # APK, direct-install
eas build --profile production --platform android   # AAB, for Play Store
eas build --profile production --platform ios       # IPA, for App Store

# Submit (after build)
eas submit --profile production --platform android  # uploads AAB
eas submit --profile production --platform ios

# OTA updates (after first release)
eas update --branch production --message "Fix invoice PDF"

# Credentials
eas credentials                                     # manage signing keys
```

If anything in this runbook breaks, ping me with the exact error log line and I'll patch the relevant file.
