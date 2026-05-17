# A1 Field Pro — Mobile (Expo / React Native)

A native iOS + Android companion app for technicians. Same backend as the web app — full API parity, single sign-on.

> **Build environment:** This folder is **source-code only**. The Emergent web preview cannot build or run React Native. You must clone this folder to your local machine (Mac for iOS, any OS for Android) and run `npx expo start`.

## Quick start (local machine)

```bash
cd mobile
npm install            # or: yarn / pnpm install
cp .env.example .env   # then edit API_URL to your A1 Field Pro backend
npx expo start         # scan QR with Expo Go app, or press i / a for sim
```

## Tech stack
- [Expo SDK 51](https://docs.expo.dev/) — React Native framework with built-in routing, secure storage, native modules.
- [Expo Router](https://docs.expo.dev/router/introduction/) — file-based routing.
- [Axios](https://axios-http.com/) — HTTP client with the same base URL pattern as the web app.
- [Expo SecureStore](https://docs.expo.dev/versions/latest/sdk/securestore/) — keychain-backed JWT storage.

## What's included (MVP)
- **`app/(auth)/login.tsx`** — email/password login against `POST /api/auth/login`.
- **`app/(tabs)/index.tsx`** — Today's jobs list (filtered by date, sorted by scheduled_at).
- **`app/(tabs)/jobs/[id].tsx`** — job detail with Start / Complete buttons and a "Pay now" CTA that opens the customer's Stripe URL in the system browser.
- **`app/(tabs)/profile.tsx`** — current user info, sign out.
- **`lib/api.ts`** — axios instance + token attachment.
- **`lib/auth.ts`** — SecureStore-backed token persistence + `useAuth()` hook.

## Endpoints used
- `POST /api/auth/login` — sign in
- `GET /api/auth/me` — current user
- `GET /api/jobs?mine=true` — technician's jobs
- `PATCH /api/jobs/{id}` — status changes

## Future hooks
- Push notifications via `expo-notifications` (server is already VAPID-ready — needs FCM/APNs token format adapter)
- Camera-based photo upload (`expo-image-picker` → POST `/api/jobs/{id}/photos`)
- Signature capture (`react-native-signature-canvas`)
- Offline queue (re-use the SW strategy — but with `react-native-async-storage`)

## App store distribution
Build with [EAS Build](https://docs.expo.dev/eas/) when ready:
```bash
npx eas build --platform ios       # needs Apple Developer account
npx eas build --platform android   # needs Google Play account
```
