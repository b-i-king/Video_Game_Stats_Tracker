// Light Climb — offline score queue (SW path: Chrome / Android / Telegram Desktop)
// iOS/Safari falls back to the localStorage path in light-climb.html

const SYNC_TAG   = 'lc-score-sync';
const SCORE_PATH = '/api/game/score';
const DB_NAME    = 'lc-sw-queue';
const DB_VER     = 1;
const STORE      = 'scores';

// ── IndexedDB helpers ─────────────────────────────────────────────────────────
function openDB() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB_NAME, DB_VER);
    r.onupgradeneeded = e => e.target.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
    r.onsuccess = e => res(e.target.result);
    r.onerror   = e => rej(e.target.error);
  });
}

async function enqueue(item) {
  const db = await openDB();
  return new Promise((res, rej) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).add(item);
    tx.oncomplete = res;
    tx.onerror    = e => rej(e.target.error);
  });
}

async function getAll() {
  const db = await openDB();
  return new Promise((res, rej) => {
    const tx = db.transaction(STORE, 'readonly');
    const r  = tx.objectStore(STORE).getAll();
    r.onsuccess = e => res(e.target.result);
    r.onerror   = e => rej(e.target.error);
  });
}

async function remove(id) {
  const db = await openDB();
  return new Promise((res, rej) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = res;
    tx.onerror    = e => rej(e.target.error);
  });
}

// ── Fetch intercept ───────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'POST' || !req.url.includes(SCORE_PATH)) return;

  event.respondWith(
    fetch(req.clone()).catch(async () => {
      try {
        const body = await req.clone().json();
        const auth = req.headers.get('Authorization') || '';
        await enqueue({ body, auth, ts: Date.now() });
        if ('sync' in self.registration) {
          await self.registration.sync.register(SYNC_TAG);
        }
        console.log('[SW] Score queued:', body.score + 'm');
      } catch (e) {
        console.error('[SW] Queue error:', e);
      }
      // Return 202 so the game treats it as handled — no error shown to player
      return new Response(JSON.stringify({ queued: true }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      });
    })
  );
});

// ── Background Sync ───────────────────────────────────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === SYNC_TAG) event.waitUntil(flushQueue());
});

async function flushQueue() {
  const items = await getAll();
  for (const item of items) {
    try {
      const r = await fetch(SCORE_PATH, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': item.auth },
        body:    JSON.stringify(item.body),
      });
      if (r.ok) {
        await remove(item.id);
        console.log('[SW] Flushed:', item.body.score + 'm');
      } else if (r.status === 401) {
        // JWT expired — nothing the SW can do; drop to avoid infinite retries
        await remove(item.id);
        console.warn('[SW] JWT expired — queued score dropped');
      }
      // 5xx / network error: leave in queue, retry on next sync event
    } catch (e) {
      console.error('[SW] Flush error — will retry:', e);
    }
  }
}
