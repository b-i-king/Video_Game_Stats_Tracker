# Video Game Stats Tracker — Mobile App

Expo / React Native app for the Video Game Stats Tracker. Runs on iOS, Android, and Web via Expo Go during development. Production builds are distributed through EAS Build.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Expo SDK 54 / React Native 0.81 |
| Language | TypeScript |
| Navigation | React Navigation v7 (bottom tabs + native stack) |
| Auth | Google OAuth via `expo-auth-session` |
| Font | Fira Code (`@expo-google-fonts/fira-code`) |
| Storage | `expo-secure-store` (JWT), `@react-native-async-storage` |
| Notifications | `expo-notifications` (push) |
| Build & Distribution | EAS Build |
| Backend API | Flask (Render) |
| Database | AWS Redshift Serverless |

---

## Project Structure

```
mobile/
├── App.tsx                     # Entry — font loading, push notifications, nav container
├── app.json                    # Expo config (bundle ID, splash, icons)
├── eas.json                    # EAS Build profiles (development, preview, production)
├── src/
│   ├── api/
│   │   └── stats.ts            # All Flask API client functions (mirrors web/lib/api.ts)
│   ├── auth/
│   │   └── useAuth.ts          # AuthContext — Google sign-in, JWT storage, isTrusted flag
│   ├── components/
│   │   ├── PickerModal.tsx     # Bottom-sheet modal replacing <select> for native dropdowns
│   │   ├── StatCard.tsx        # Reusable stat display card
│   │   ├── InteractiveChart.tsx # WebView for GCS-hosted Plotly HTML
│   │   └── NotificationBadge.tsx
│   ├── lib/
│   │   └── constants.ts        # Genres, match types, platforms (mirrors web/lib/constants.ts)
│   ├── navigation/
│   │   └── AppNavigator.tsx    # Bottom tab + stack navigator
│   ├── notifications/
│   │   └── pushNotifications.ts # Push token registration
│   └── screens/
│       ├── LoginScreen.tsx
│       ├── StatsEntryScreen.tsx # Main stat entry form
│       ├── DashboardScreen.tsx
│       ├── StatsHistoryScreen.tsx
│       ├── LeaderboardScreen.tsx
│       └── ProfileScreen.tsx
└── assets/                     # App icons, splash screen images
```

---

## Screens

| Screen | Description |
|---|---|
| Login | Google OAuth sign-in — JWT stored via `expo-secure-store` |
| Stats Entry | Log game stats (full feature parity with the web app) |
| Stats History | View stat history + embedded interactive Plotly chart (GCS WebView) |
| Dashboard | WebView wrapping the Flask `/dashboard` live OBS overlay |
| Leaderboard | Community rankings |
| Profile | User info + sign out |

---

## Prerequisites

- Node.js 20+
- Expo CLI: `npm install -g expo`
- EAS CLI (for builds): `npm install -g eas-cli`
- Expo Go app on your device (for development)
- A Google OAuth 2.0 client with iOS, Android, and Web client IDs
- A running instance of the Flask backend (see root `flask_app.py`)

---

## Local Setup

### 1. Install dependencies

```bash
cd mobile
npm install
```

> **Fira Code font** — if not already installed:
> ```bash
> npx expo install @expo-google-fonts/fira-code
> ```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in all values:

```env
# Flask backend URL (no trailing slash)
EXPO_PUBLIC_API_URL=https://your-flask-app.onrender.com

# Google OAuth client IDs — from Google Cloud Console
# Each platform requires its own OAuth 2.0 client ID
EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS=YOUR_IOS_CLIENT_ID.apps.googleusercontent.com
EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID=YOUR_ANDROID_CLIENT_ID.apps.googleusercontent.com
EXPO_PUBLIC_GOOGLE_CLIENT_ID_WEB=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
```

All `EXPO_PUBLIC_` variables are bundled at build time. Do **not** put secrets here.

### 3. Run in development

```bash
# Start Expo dev server — scan QR code with Expo Go
npm start

# Or target a specific platform
npm run android
npm run ios
```

---

## Authentication Flow

```
User taps "Sign in with Google"
  → expo-auth-session opens Google OAuth in browser
  → Google returns identity token
  → useAuth calls POST /api/login on Flask
      with { email } + X-API-KEY header
  → Flask looks up / creates user in Redshift dim.dim_users
  → Flask returns { token, is_trusted }
  → JWT stored in expo-secure-store
  → isTrusted = user.role === 'trusted' || user.role === 'admin'
```

**Roles:**
- `trusted` / `admin` — full access: stat entry, OBS controls, queue management
- `guest` — read-only preview on StatsEntryScreen

To mark a user as trusted, add their Google email to the `TRUSTED_EMAILS` environment variable on the Flask backend.

---

## Key Mobile-Specific Patterns

### PickerModal (native dropdowns)

React Native has no `<select>`. All dropdowns use `PickerModal` — a bottom-sheet `Modal` + `FlatList`:

```tsx
<PickerModal
  visible={showFranchisePicker}
  title="Select Franchise"
  options={franchises}
  selected={selectedFranchise}
  onSelect={(val) => { setSelectedFranchise(val); setShowFranchisePicker(false); }}
  onClose={() => setShowFranchisePicker(false)}
/>
```

### Global Font Application

Fira Code is applied to all `Text` and `TextInput` globally in `App.tsx` after fonts load:

```tsx
Text.defaultProps = { style: { fontFamily: 'FiraCode_400Regular' } };
TextInput.defaultProps = { style: { fontFamily: 'FiraCode_400Regular' } };
```

### TextInput Color

React Native's `TextInput` does not accept a `color` prop directly. Always put it inside `style`:

```tsx
// ✅ Correct
<TextInput style={[styles.input, { color: '#FFF' }]} />

// ❌ Wrong — TypeScript error
<TextInput color="#FFF" />
```

### Stat Payload Format

Stats are submitted as an array of `StatRow` objects:

```ts
stats: [
  { stat_type: "Kills", stat_value: 24 },
  { stat_type: "Deaths", stat_value: 8 },
]
```

---

## Building for Distribution (EAS)

```bash
# One-time: log in and link to EAS project
eas login
eas init   # only needed if starting fresh

# Preview build (internal testing / TestFlight)
eas build --profile preview --platform all

# Production build (App Store / Google Play)
eas build --profile production --platform all

# Submit to stores
eas submit --platform ios
eas submit --platform android
```

---

## Push Notifications

Push tokens are registered on app launch via `src/notifications/pushNotifications.ts`. To send a notification from the Flask backend:

```python
import requests

requests.post("https://exp.host/--/api/v2/push/send", json={
    "to": "<ExponentPushToken[...]>",
    "title": "Stats posted!",
    "body": "Eliminations: 28"
})
```

---

## Costs

| Item | Cost |
|---|---|
| Expo (development + OTA updates) | Free |
| EAS Build | Free tier (30 builds/month) |
| Apple Developer Program | $99/yr (required for App Store + TestFlight) |
| Google Play | $25 one-time |
| Expo Push Notifications | Free |

---

## Adapting for Another Application

To reuse this template for a different app:

1. **Update `app.json`** — change `name`, `slug`, `bundleIdentifier` (iOS), `package` (Android), and `icon`/`splash` assets. Update `extra.eas.projectId` with your EAS project ID.
2. **Replace `src/api/stats.ts`** — update API functions for your backend. The `Authorization: Bearer <jwt>` header pattern works for any Flask backend using the same JWT setup.
3. **Replace `src/lib/constants.ts`** — swap domain-specific options for your use case.
4. **Replace `src/screens/StatsEntryScreen.tsx`** — the `PickerModal` + form pattern works for any data-entry screen.
5. **Update `src/auth/useAuth.ts`** — change Google client IDs and the Flask login endpoint if your backend differs.
6. **Update CORS on Flask** — add your app's origin to the `CORS` origins list in `flask_app.py` if needed.

---

## Scripts

| Command | Description |
|---|---|
| `npm start` | Start Expo dev server |
| `npm run android` | Start on Android |
| `npm run ios` | Start on iOS |
| `npm run build:preview` | EAS preview build (all platforms) |
| `npm run build:production` | EAS production build (all platforms) |
