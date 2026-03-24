# Video Game Stats Tracker — Web App

Next.js 16 front-end for the Video Game Stats Tracker. Deployed on Vercel, authenticated via Google OAuth, and backed by a Flask REST API on Render with AWS Redshift as the data warehouse.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 3 |
| Auth | NextAuth v4 (Google OAuth) |
| Font | Fira Code (Google Fonts) |
| Deployment | Vercel |
| Backend API | Flask (Render) |
| Database | AWS Redshift Serverless |

---

## Project Structure

```
web/
├── app/
│   ├── layout.tsx          # Root layout — metadata, SEO, JSON-LD, Navbar
│   ├── page.tsx            # Home / landing page
│   ├── stats/              # Stats entry form (trusted users only)
│   ├── privacy/            # Privacy policy
│   ├── terms/              # Terms of service
│   ├── data-deletion/      # GDPR data deletion page
│   └── api/
│       └── auth/[...nextauth]/  # NextAuth route handler
├── components/
│   ├── Navbar.tsx          # Top nav with Google sign-in / sign-out
│   ├── StatsForm.tsx       # Main stat entry form (game, player, stats)
│   ├── GetStartedButton.tsx # Client-side Google sign-in CTA
│   └── RenderWarmup.tsx    # Fires /health ping on page load to pre-warm Render + Redshift
├── lib/
│   ├── api.ts              # All Flask API client functions
│   ├── auth.ts             # NextAuth config — Google provider + Flask JWT exchange
│   └── constants.ts        # Genres, match types, platforms, etc.
└── types/
    └── next-auth.d.ts      # NextAuth session type extensions
```

---

## Prerequisites

- Node.js 20+
- A Google OAuth 2.0 client (Cloud Console)
- A running instance of the Flask backend (see root `flask_app.py`)

---

## Local Setup

### 1. Install dependencies

```bash
cd web
npm install
```

### 2. Configure environment variables

Copy `.env.local.example` to `.env.local` and fill in all values:

```env
# Flask backend URL (local or Render)
FLASK_API_URL=https://your-app.onrender.com
NEXT_PUBLIC_FLASK_API_URL=https://your-app.onrender.com

# Static API key — must match API_KEY on the Flask side
FLASK_API_KEY=your-flask-api-key-here

# Google OAuth — from Google Cloud Console
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET

# NextAuth — generate with: openssl rand -base64 32
NEXTAUTH_SECRET=replace-me-with-a-random-32-char-string
NEXTAUTH_URL=http://localhost:3000
```

### 3. Run in development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Authentication Flow

```
User clicks "Get Started"
  → signIn("google")                          [NextAuth / Google OAuth]
  → Google returns identity token
  → NextAuth JWT callback calls POST /api/login on Flask
      with { email } + X-API-KEY header
  → Flask looks up / creates user in Redshift dim.dim_users
  → Flask returns { token, is_trusted }
  → NextAuth stores Flask JWT + role in session
  → User lands on /stats
```

**Roles:**
- `trusted` — can submit stats, access all form fields, set live game, manage OBS
- `guest` — can view the app but sees a read-only preview on /stats

To mark a user as trusted, add their Google email to the `TRUSTED_EMAILS` environment variable on the Flask side.

---

## Deployment (Vercel)

1. Push to GitHub. Vercel auto-deploys on every push to `main`.
2. Set all environment variables from `.env.local.example` in the Vercel dashboard under **Settings → Environment Variables**.
3. Set `NEXTAUTH_URL` to your production Vercel URL (e.g. `https://your-app.vercel.app`).
4. Add your Vercel domain to the **Authorized JavaScript origins** and **Authorized redirect URIs** in Google Cloud Console:
   - Origin: `https://your-app.vercel.app`
   - Redirect URI: `https://your-app.vercel.app/api/auth/callback/google`

---

## CI — GitHub Actions

`.github/workflows/vercel_checks.yml` runs on every push/PR touching `web/`:

- **Lint** — `eslint .` using the ESLint 9 flat config in `eslint.config.js`
- **Type check** — `npx tsc --noEmit`

Both jobs report their status back to Vercel via `vercel/repository-dispatch/actions/status@v1`.

---

## Adapting for Another Application

To reuse this template for a different app:

1. **Replace the Flask backend URL** — update `FLASK_API_URL` in `.env.local`.
2. **Update `lib/api.ts`** — replace or extend API functions to match your backend's endpoints.
3. **Update `lib/constants.ts`** — swap out game-specific dropdowns (genres, platforms, etc.) for your domain.
4. **Update `lib/auth.ts`** — the Google → Flask JWT exchange pattern works for any Flask backend; just ensure your `/api/login` endpoint returns `{ token, is_trusted }`.
5. **Replace `StatsForm.tsx`** — the form structure and Section component pattern can wrap any data-entry use case.
6. **Update SEO** — edit the `metadata` export in `app/layout.tsx` and the JSON-LD structured data block.
7. **Update CORS** — add your Vercel domain to the `CORS` origins list in `flask_app.py`.

---

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start development server |
| `npm run build` | Production build |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npx tsc --noEmit` | Run TypeScript type check |
