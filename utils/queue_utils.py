"""
utils/queue_utils.py
Render Postgres connection and post_queue CRUD helpers.
All game stat data stays in Redshift; only the post queue lives here.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def _get_conn():
    """Open a fresh connection to Render Postgres."""
    database_url = os.environ.get("QUEUE_DATABASE_URL")
    if not database_url:
        raise RuntimeError("QUEUE_DATABASE_URL env var not set")
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


def ensure_post_queue_table():
    """
    Create post_queue table if it does not exist.
    Idempotent — safe to call on every app start.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS post_queue (
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
    Insert a pending post into post_queue.
    Returns the new queue_id.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO post_queue (player_id, platform, image_url, caption, status, scheduled_at)
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
                FROM post_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED;
            """)
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE post_queue SET status = 'processing' WHERE queue_id = %s;",
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
                "UPDATE post_queue SET status = %s WHERE queue_id = %s;",
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
                FROM post_queue
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
                "UPDATE post_queue SET status = 'pending' WHERE status = 'failed';"
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
                UPDATE post_queue
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
                DELETE FROM post_queue
                WHERE status = 'sent'
                  AND created_at < NOW() - INTERVAL '%s days';
            """, (days,))
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()
