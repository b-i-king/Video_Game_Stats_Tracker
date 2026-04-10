"""
utils/queue_utils.py
post_queue CRUD helpers — reads from app.post_queue on personal Supabase.
Uses the same DB env vars as flask_app.py (no separate QUEUE_DATABASE_URL needed).
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def _get_conn():
    """Open a fresh connection to personal Supabase (same creds as Flask)."""
    return psycopg2.connect(
        host=os.environ["DB_URL"],
        port=int(os.environ.get("DB_PORT", 6543)),
        database=os.environ.get("DB_NAME", "postgres"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="require",
        cursor_factory=RealDictCursor,
    )


def ensure_post_queue_table():
    """
    Skipped on Supabase — table managed via supabase_schema.sql.
    Kept for Redshift/legacy compatibility only.
    """
    if os.environ.get("DB_TYPE") == "supabase":
        print("Skipping ensure_post_queue_table(): managed via supabase_schema.sql.")
        return
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app.post_queue (
                    queue_id     SERIAL PRIMARY KEY,
                    player_id    VARCHAR(50),
                    platform     VARCHAR(20),
                    image_url    VARCHAR(1000),
                    caption      TEXT,
                    status       VARCHAR(20) DEFAULT 'pending',
                    scheduled_at TIMESTAMP,
                    created_at   TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()
    finally:
        conn.close()


def enqueue_post(player_id, platform, image_url, caption, scheduled_at=None):
    """
    Insert a pending post into app.post_queue.
    Returns the new queue_id.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO app.post_queue (player_id, platform, image_url, caption, status, scheduled_at)
                VALUES (%s, %s, %s, %s, 'pending', %s)
                RETURNING queue_id;
            """, (str(player_id), platform, image_url, caption, scheduled_at))
            row = cur.fetchone()
        conn.commit()
        return row['queue_id']
    finally:
        conn.close()


def get_oldest_pending():
    """
    Atomically claim the oldest pending item by immediately marking it
    'processing'. Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate
    processing if the cron fires concurrently.
    Returns a dict with the row, or None if the queue is empty.
    """
    conn = _get_conn()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("""
                SELECT queue_id, player_id, platform, image_url, caption
                FROM app.post_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED;
            """)
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE app.post_queue SET status = 'processing' WHERE queue_id = %s;",
                    (row['queue_id'],)
                )
        conn.commit()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_status(queue_id, status):
    """Update a queue item's status ('sent', 'failed', or 'pending')."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app.post_queue SET status = %s WHERE queue_id = %s;",
                (status, queue_id)
            )
        conn.commit()
    finally:
        conn.close()


def get_queue_counts():
    """Return {'pending': n, 'processing': n, 'sent': n, 'failed': n}."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) AS cnt
                FROM app.post_queue
                GROUP BY status;
            """)
            rows = cur.fetchall()
        counts = {'pending': 0, 'processing': 0, 'sent': 0, 'failed': 0}
        for r in rows:
            if r['status'] in counts:
                counts[r['status']] = r['cnt']
        return counts
    finally:
        conn.close()


def reset_failed_to_pending():
    """Reset all failed items back to pending. Returns count of rows reset."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app.post_queue SET status = 'pending' WHERE status = 'failed';"
            )
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()


def reset_stale_processing(minutes=10):
    """
    Reset 'processing' items older than `minutes` back to 'pending'.
    Guards against rows stuck in 'processing' if a cron run crashes mid-flight.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE app.post_queue
                SET status = 'pending'
                WHERE status = 'processing'
                  AND created_at < NOW() - INTERVAL '%s minutes';
            """, (minutes,))
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()


def purge_old_sent(days=7):
    """Delete sent rows older than `days` days. Returns count deleted."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM app.post_queue
                WHERE status = 'sent'
                  AND created_at < NOW() - INTERVAL '%s days';
            """, (days,))
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()
