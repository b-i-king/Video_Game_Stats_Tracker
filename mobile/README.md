# Game Tracker — Mobile App

React Native + Expo companion app for the Game Tracker platform. Targets iOS, Android, and web from a single TypeScript codebase.

---

## Screens

| Screen | Description |
|---|---|
| Login | Email/password sign-in — JWT stored via `expo-secure-store` |
| Stats Entry | Log game stats, mirrors `pages/2_Stats.py` — calls `POST /api/add_stats` |
| Stats History | View stat history + embedded interactive Plotly chart (GCS WebView) |
| Dashboard | WebView wrapping the Flask `/dashboard` live overlay |
| Leaderboard | Community rankings — Supabase realtime (placeholder until wired) |
| Profile | User info + sign out |

---

## Prerequisites

- Node.js 18+
- Expo CLI: `npm install -g expo-cli`
- Expo Go app on your phone (for development, no build needed)
- For production builds: EAS CLI (`npm install -g eas-cli`) + Expo account

---

## Setup

```bash
cd mobile
npm install
cp .env.example .env
```

Edit `.env` and set `EXPO_PUBLIC_API_URL` to your Flask API URL.

---

## Running

```bash
# Start dev server — scan QR with Expo Go
npx expo start

# Run on specific platform
npx expo start --ios
npx expo start --android
npx expo start --web
```

---

## Building for Distribution

```bash
# One-time: link to EAS
npx eas init

# Preview build (internal testing / TestFlight)
npx eas build --profile preview --platform all

# Production build (App Store / Google Play)
npx eas build --profile production --platform all
```

---

## Project Structure

```
mobile/
├── App.tsx                        # Root — wraps NavigationContainer + AuthProvider
├── app.json                       # Expo config (bundle ID, icon, splash)
├── eas.json                       # EAS build profiles
├── src/
│   ├── api/
│   │   ├── auth.ts                # /api/login, /api/register, /api/register_push_token
│   │   └── stats.ts               # /api/add_stats, /api/get_stats, /api/get_stat_ticker
│   ├── auth/
│   │   └── useAuth.ts             # AuthContext — JWT + user state via SecureStore
│   ├── components/
│   │   ├── StatCard.tsx           # Reusable stat display with delta arrow
│   │   ├── InteractiveChart.tsx   # WebView for GCS-hosted Plotly HTML
│   │   └── NotificationBadge.tsx  # Numeric badge for tab icons
│   ├── hooks/
│   │   ├── useStats.ts            # Fetch + submit stats with loading/error state
│   │   └── useTicker.ts           # OBS ticker URL with auto-refresh interval
│   ├── navigation/
│   │   └── AppNavigator.tsx       # Bottom tab nav + auth gate
│   ├── notifications/
│   │   └── pushNotifications.ts   # Expo push token registration + local notifications
│   └── screens/
│       ├── LoginScreen.tsx
│       ├── StatsEntryScreen.tsx
│       ├── StatsHistoryScreen.tsx
│       ├── DashboardScreen.tsx
│       ├── LeaderboardScreen.tsx
│       └── ProfileScreen.tsx
└── assets/
    ├── icon.png                   # App icon (gold game controller)
    └── splash.png                 # Splash screen
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `EXPO_PUBLIC_API_URL` | Flask API base URL (no trailing slash) |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS` | Google OAuth iOS client ID |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID` | Google OAuth Android client ID |
| `EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB` | Google OAuth web client ID |
| `EXPO_PUBLIC_SUPABASE_URL` | Supabase project URL (leaderboard) |
| `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (leaderboard) |

All `EXPO_PUBLIC_` variables are bundled into the app at build time. Do **not** put secrets here.

---

## Push Notifications

Expo push tokens are registered on app launch via `notifications/pushNotifications.ts`. To send a push from the Flask backend:

```python
import requests

requests.post("https://exp.host/--/api/v2/push/send", json={
    "to": "<ExponentPushToken[...]>",
    "title": "Stats posted!",
    "body": "Eliminations: 28"
})
```

Tokens are stored when `POST /api/register_push_token` is implemented on the Flask side.

---

## Costs

| Item | Cost |
|---|---|
| Expo (development + OTA updates) | Free |
| EAS Build | Free tier (30 builds/month) |
| Apple Developer Program | $99/yr (required for App Store + TestFlight) |
| Google Play | $25 one-time |
| Expo Push Notifications | Free |
