# Bolt AI — Google AI Studio Setup

Bolt is already fully implemented. The backend (`utils/ai_utils.py`), Flask endpoint
(`/api/ask`), and frontend panel (`BoltPanel.tsx`) are all wired up and deployed.
The only step to activate it is getting a Gemini API key and adding it to Render.

---

## Current State

| Layer | File | Status |
|---|---|---|
| AI client | `utils/ai_utils.py` | Done — uses `gemini-2.0-flash` |
| Flask endpoint | `flask_app.py` → `/api/ask` | Done — JWT-gated, gracefully returns message if key missing |
| Web panel | `web/components/BoltPanel.tsx` | Done — chat UI with suggestions |
| Mobile | Deferred | After Supabase migration |
| **API key** | Render env var `GEMINI_API_KEY` | **Missing — this is the only blocker** |

---

## Step 1 — Get a Gemini API Key from Google AI Studio

1. Go to `aistudio.google.com`
2. Sign in with your Google account
3. Click **Get API key** (top-left or in the nav)
4. Click **Create API key**
5. Select **Create API key in new project** (or an existing project if you have one)
6. Copy the key — it looks like: `AIzaSy...`

**Free tier:** Gemini 2.0 Flash has a generous free tier:
- 15 requests per minute
- 1,500 requests per day
- 1 million tokens per minute

This is more than enough for personal use. No billing required at this volume.

---

## Step 2 — Add the Key to Render

1. Go to your Render dashboard → select the **Game Tracker** service
2. Click **Environment** in the left sidebar
3. Click **Add Environment Variable**
4. Set:
   - **Key:** `GEMINI_API_KEY`
   - **Value:** paste your key from Step 1
5. Click **Save Changes**
6. Render will automatically redeploy the service

---

## Step 3 — Verify It Works

Once deployed, open the web app and look for the **⚡ Bolt** panel on the Stats page.
Type any question — if the key is active you'll get a real response instead of:

> "Bolt isn't configured yet — add GEMINI_API_KEY to enable AI features."

Test prompts:
- `What's my best session?`
- `How's my Eliminations trending?`
- `Write an Instagram caption`
- `Summarize this week`

---

## What Bolt Can Do Right Now

The current implementation sends the user's prompt to Gemini with a system prompt
defining Bolt as a gaming performance assistant. **It does not yet have access to your
actual stat data** — that connection is planned for after the Supabase migration.

**Current behavior:** General gaming analysis and Instagram caption writing based on
what the user types in the prompt.

**After Supabase migration:** `build_stats_context()` in `utils/ai_utils.py` is already
written — it formats your stat rows into a string that gets injected into the prompt.
That wiring just needs to be connected in the `/api/ask` endpoint once Supabase is live.

---

## Key Rotation

Google AI Studio development keys do not expire (unlike Riot's 24h dev keys).
However, if you ever rotate it:
1. Generate a new key in AI Studio
2. Update the `GEMINI_API_KEY` env var in Render
3. No code changes needed
