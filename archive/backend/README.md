# archive/backend

This directory holds the legacy Flask backend after the FastAPI cut-over.

## Cut-over procedure (1-day)

1. **Deploy FastAPI** as a new Render service pointing at the same Supabase DB.
   - Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - Add all env vars from the Flask service.

2. **Smoke-test** the FastAPI service URL against `/health` and `/db_health`.
   Run a quick end-to-end check on the routes that are fully migrated:
   - `GET /api/get_players`
   - `GET /api/get_games`
   - `POST /api/login`
   - `POST /api/set_live_state`

3. **Flip the Vercel env var**:
   `NEXT_PUBLIC_FLASK_API_URL` → new FastAPI Render URL

4. **Monitor** for 24 hours.  Roll back by reverting the Vercel env var.

5. **Archive Flask**:
   ```bash
   git mv flask_app.py archive/backend/flask_app.py
   git commit -m "archive: move flask_app.py to archive/backend after FastAPI cut-over"
   ```

6. Disable / delete the old Render Flask service.

## What lives here after cut-over

| File | Description |
|---|---|
| `flask_app.py` | Original Flask monolith (~3 000 lines) |

The file is kept for reference — do not redeploy it.
